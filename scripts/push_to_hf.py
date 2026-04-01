#!/usr/bin/env python3
"""
Push Unified Evaluation Dataset to Hugging Face
==============================================
Pulls GAIA (benign control), ahsanayub/malicious-prompts, and codesagar/malicious-llm-prompts.
Homogenizes them into a standard schema and pushes to akane69/Agent-Glass.

Requirements:
    pip install datasets pandas scikit-learn huggingface_hub
"""

import os
import uuid
import pandas as pd
from datasets import load_dataset, Dataset, DatasetDict
from sklearn.model_selection import train_test_split
from huggingface_hub import login

# Configuration
HF_REPO_ID = "akane69/Agent-Glass"
HF_TOKEN = os.getenv("HF_TOKEN")

def load_gaia():
    print("Loading GAIA dataset...")
    try:
        ds = load_dataset("gaia-benchmark/GAIA", "2023_all", split="validation", token=HF_TOKEN)
    except Exception as e:
        print(f"Failed to load GAIA: {e}")
        return []

    samples = []
    for row in ds:
        q = row.get("Question", "").strip()
        if not q:
            continue
        samples.append({
            "sample_id": str(uuid.uuid4()),
            "source": "gaia",
            "category": "good",
            "expected_decision": "approve",
            "prompt": q,
            "metadata": {
                "gaia_level": row.get("Level", 1),
                "file_path": row.get("file_name", ""),
                "task_id": row.get("task_id", "")
            }
        })
    print(f"  -> Extracted {len(samples)} GAIA samples.")
    return samples

def load_ahsanayub():
    print("Loading ahsanayub/malicious-prompts...")
    samples = []
    try:
        for split_name in ["train", "test"]:
            ds = load_dataset("ahsanayub/malicious-prompts", split=split_name, token=HF_TOKEN)
            for row in ds:
                q = row.get("text", "")
                if not q:
                    continue
                is_mal = (row.get("label") == 1)
                samples.append({
                    "sample_id": str(uuid.uuid4()),
                    "source": "ahsanayub",
                    "category": "malicious" if is_mal else "good",
                    "expected_decision": "deny" if is_mal else "approve",
                    "prompt": q,
                    "metadata": {"original_label": row.get("label")}
                })
    except Exception as e:
        print(f"Failed to load ahsanayub: {e}")
    print(f"  -> Extracted {len(samples)} ahsanayub samples.")
    return samples

def load_codesagar():
    print("Loading codesagar/malicious-llm-prompts...")
    samples = []
    try:
        ds = load_dataset("codesagar/malicious-llm-prompts", split="train", token=HF_TOKEN)
        for row in ds:
            q = row.get("prompt", "")
            if not q:
                continue
            is_mal = row.get("malicious", False)
            samples.append({
                "sample_id": str(uuid.uuid4()),
                "source": "codesagar",
                "category": "malicious" if is_mal else "good",
                "expected_decision": "deny" if is_mal else "approve",
                "prompt": q,
                "metadata": {"attack_type": row.get("attack_type")}
            })
    except Exception as e:
        print(f"Failed to load codesagar: {e}")
    print(f"  -> Extracted {len(samples)} codesagar samples.")
    return samples

def main():
    if not HF_TOKEN:
        print("HF_TOKEN not found in environment. Please set it in .env.")
        return

    # Login to HF Hub
    login(token=HF_TOKEN)

    gaia_samples = load_gaia()
    ahsan_samples = load_ahsanayub()
    sagar_samples = load_codesagar()

    all_samples = gaia_samples + ahsan_samples + sagar_samples

    if not all_samples:
        print("No samples loaded. Exiting.")
        return

    df = pd.DataFrame(all_samples)
    print(f"\nTotal Unified Samples: {len(df)}")

    # Add stratify key
    df['stratify_key'] = df['category'] + "_" + df['source']
    counts = df['stratify_key'].value_counts()
    valid_keys = counts[counts >= 3].index
    df = df[df['stratify_key'].isin(valid_keys)].copy()

    # Stratified splits
    train_df, temp_df = train_test_split(df, test_size=0.30, random_state=42, stratify=df['stratify_key'])
    val_df, test_df = train_test_split(temp_df, test_size=0.50, random_state=42, stratify=temp_df['stratify_key'])

    # Create DatasetDict
    ds_dict = DatasetDict({
        "train": Dataset.from_pandas(train_df.drop(columns=['stratify_key'])),
        "validation": Dataset.from_pandas(val_df.drop(columns=['stratify_key'])),
        "test": Dataset.from_pandas(test_df.drop(columns=['stratify_key']))
    })

    print("\nPushing to Hugging Face Hub...")
    ds_dict.push_to_hub(HF_REPO_ID, private=True)
    print(f"Successfully pushed dataset to https://huggingface.co/datasets/{HF_REPO_ID}")

if __name__ == "__main__":
    main()
