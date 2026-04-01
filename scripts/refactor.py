#!/usr/bin/env python3
import os
import re

SERVICES = [
    "agent",
    "critic",
    "embedder",
    "evaluator",
    "router",
    "synthetic-gen",
    "trace-gateway"
]

def refactor_dockerfiles():
    for svc in SERVICES:
        dockerfile_path = f"services/{svc}/Dockerfile"
        if not os.path.exists(dockerfile_path):
            continue
        with open(dockerfile_path, "r") as f:
            content = f.read()
        
        # Replace COPY requirements.txt . -> COPY services/{svc}/requirements.txt .
        content = re.sub(r"COPY requirements\.txt \.", f"COPY services/{svc}/requirements.txt .", content)
        # Replace COPY app ./app -> COPY services/{svc}/app ./app\nCOPY pkg ./pkg
        if "COPY pkg ./pkg" not in content:
            content = re.sub(r"COPY app \./app", f"COPY services/{svc}/app ./app\nCOPY pkg ./pkg", content)
            
        with open(dockerfile_path, "w") as f:
            f.write(content)

def refactor_compose():
    compose_path = "infra/compose.yaml"
    with open(compose_path, "r") as f:
        content = f.read()
    
    for svc in SERVICES:
        # replace `build: ../services/{svc}` with:
        # build:
        #   context: ..
        #   dockerfile: services/{svc}/Dockerfile
        
        old_build = f"build: ../services/{svc}"
        new_build = f"build:\n      context: ..\n      dockerfile: services/{svc}/Dockerfile"
        content = content.replace(old_build, new_build)
            
    with open(compose_path, "w") as f:
        f.write(content)

def refactor_imports():
    for svc in SERVICES:
        main_path = f"services/{svc}/app/main.py"
        if not os.path.exists(main_path):
            continue
            
        with open(main_path, "r") as f:
            content = f.read()
            
        # We want to remove all lines that match variables = os.getenv(...)
        # and insert `from pkg.config.env import *`
        
        lines = content.splitlines()
        new_lines = []
        has_imported = False
        
        for line in lines:
            if re.match(r"^[A-Z_]+\s*=\s*os\.getenv\(", line) or re.match(r"^LOOP_LOOKBACK\s*=", line) or re.match(r"^LOOP_THRESHOLD\s*=", line):
                if not has_imported:
                    new_lines.append("from pkg.config.env import *")
                    has_imported = True
            else:
                new_lines.append(line)
                
        with open(main_path, "w") as f:
            f.write("\n".join(new_lines) + "\n")

if __name__ == "__main__":
    refactor_dockerfiles()
    refactor_compose()
    refactor_imports()
    print("Refactor complete.")
