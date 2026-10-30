"""Start all AI mock services in one process (multiprocess)."""
import multiprocessing
import uvicorn


def run(module: str, port: int):
    uvicorn.run(module, host="127.0.0.1", port=port, log_level="warning")


SERVICES = [
    ("pose.main:app", 8101),
    ("pose_kb.main:app", 8102),
    ("video_gen.main:app", 8103),
    ("parsing.main:app", 8104),
    ("visual_encoder.main:app", 8105),
    ("behavior.main:app", 8106),
    ("video_cot.main:app", 8107),
]


def main():
    import os
    import sys
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai_services"))
    sys.path.insert(0, root)
    os.chdir(root)
    procs = []
    for mod, port in SERVICES:
        p = multiprocessing.Process(target=run, args=(mod, port), daemon=True)
        p.start()
        procs.append(p)
        print(f"started {mod} on {port}")
    for p in procs:
        p.join()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
