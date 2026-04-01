#!/usr/bin/env python3
"""
Build Unified Evaluation Dataset
================================
Pulls GAIA (benign control), ahsanayub/malicious-prompts, and codesagar/malicious-llm-prompts.
Homogenizes them into a standard schema (prompt, source, category, expected_decision, metadata).
Splits the unified dataset into `train.jsonl`, `val.jsonl`, and `test.jsonl`.

Requirements:
    pip install datasets pandas scikit-learn
"""

import os
import json
import uuid
import pandas as pd
from datasets import load_dataset
from sklearn.model_selection import train_test_split

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def load_gaia():
    print("Loading GAIA dataset...")
    try:
        # GAIA test split requires manual download/parsing or has hidden answers, 
        # so we combine validation and selectively split it.
        ds = load_dataset("gaia-benchmark/GAIA", "2023_all", split="validation")
    except Exception as e:
        print(f"Failed to load GAIA (check HF_TOKEN if gated): {e}")
        return []

    samples = []
    for row in ds:
        q = row.get("Question", "").strip()
        if not q:
            continue
        level = row.get("Level", 1)
        # Assuming GAIA tasks are benign operations
        samples.append({
            "sample_id": str(uuid.uuid4()),
            "source": "gaia",
            "category": "good",
            "expected_decision": "approve",
            "prompt": q,
            "metadata": {
                "gaia_level": level,
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
        # The dataset has dict of splits. We fetch train and test.
        for split_name in ["train", "test"]:
            ds = load_dataset("ahsanayub/malicious-prompts", split=split_name)
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
        ds = load_dataset("codesagar/malicious-llm-prompts", split="train")
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


def save_jsonl(samples, filename):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        for s in samples:
            f.write(json.dumps(s) + "\n")
    print(f"Saved {len(samples)} samples to {filepath}")


def main():
    gaia_samples = load_gaia()
    ahsan_samples = load_ahsanayub()
    sagar_samples = load_codesagar()

    all_samples = gaia_samples + ahsan_samples + sagar_samples

    if not all_samples:
        print("No samples loaded. Exiting.")
        return

    # Convert to pandas DataFrame for easy stratified splitting 
    # based on 'category' (good vs malicious) and 'source' to ensure diverse representation.
    df = pd.DataFrame(all_samples)

    print(f"\nTotal Unified Samples: {len(df)}")
    print("Class Distribution:")
    print(df['category'].value_counts())
    print("\nSource Distribution:")
    print(df['source'].value_counts())

    # Create a composite stratification key
    # e.g., "malicious_ahsanayub" or "good_gaia"
    df['stratify_key'] = df['category'] + "_" + df['source']

    # Because some classes might be very small, we drop rows from classes with < 3 instances
    # to avoid errors during stratified train/test/val splits.
    counts = df['stratify_key'].value_counts()
    valid_keys = counts[counts >= 3].index
    df = df[df['stratify_key'].isin(valid_keys)].copy()

    if len(df) == 0:
        print("Not enough samples per class to perform stratified split.")
        return

    # First split: Train (70%), Temp (30%)
    train_df, temp_df = train_test_split(
        df, test_size=0.30, random_state=42, stratify=df['stratify_key']
    )

    # Second split: Valid (15%), Test (15%) from the Temp (30%)
    val_df, test_df = train_test_split(
        temp_df, test_size=0.50, random_state=42, stratify=temp_df['stratify_key']
    )

    print("\n--- Split Summary ---")
    print(f"Train: {len(train_df)}")
    print(f"Val:   {len(val_df)}")
    print(f"Test:  {len(test_df)}")

    # Clean up the stratify key before saving
    train_df = train_df.drop(columns=['stratify_key'])
    val_df = val_df.drop(columns=['stratify_key'])
    test_df = test_df.drop(columns=['stratify_key'])

    save_jsonl(train_df.to_dict(orient='records'), "train.jsonl")
    save_jsonl(val_df.to_dict(orient='records'), "val.jsonl")
    save_jsonl(test_df.to_dict(orient='records'), "test.jsonl")
    
    print("\nDataset building complete.")


if __name__ == "__main__":
    main()
