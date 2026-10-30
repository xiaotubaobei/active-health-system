"""端到端假闭环冒烟：登录 → 体适能 → 处方 → 会话 → CoT报告 → 处方版本+1"""
import sys
import time
import httpx

API = "http://127.0.0.1:8000"
AI_PORTS = [8101, 8102, 8103, 8104, 8105, 8106, 8107]


def wait_url(url: str, timeout: float = 30.0):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code < 500:
                return True
        except Exception as e:
            last = e
        time.sleep(0.5)
    raise RuntimeError(f"timeout waiting {url}: {last}")


def main():
    print("1) check API /health")
    wait_url(f"{API}/health")
    h = httpx.get(f"{API}/health", timeout=5).json()
    print("   ", h)

    print("2) check AI stubs /health")
    for p in AI_PORTS:
        try:
            r = httpx.get(f"http://127.0.0.1:{p}/health", timeout=2)
            print(f"   :{p}", r.json().get("service") or r.json())
        except Exception as e:
            print(f"   :{p} DOWN ({e}) — backend will use local_fallback")

    c = httpx.Client(base_url=API, timeout=30.0)

    print("3) login")
    login = c.post("/auth/login", json={"username": "demo", "password": "123456"}).json()
    user = login["user"]
    uid = user["id"]
    print("   user_id=", uid, "role=", user["role"])

    print("4) update profile")
    c.put(
        f"/users/me?user_id={uid}",
        json={
            "age_group": "middle_age",
            "height_cm": 172,
            "weight_kg": 78,
            "goal": "fitness",
            "chronic_tags": [],
        },
    )

    print("5) fitness assess")
    fit = c.post(
        "/fitness/assess",
        json={
            "user_id": uid,
            "scale_id": "middle_elder",
            "scores": {"bmi": 80, "strength": 70, "flexibility": 65, "balance": 60},
        },
    ).json()
    print("   total=", fit.get("total_score"), "level=", fit.get("level"))

    print("6) generate prescription")
    presc = c.post("/prescriptions/generate", json={"user_id": uid}).json()
    pid = presc["id"]
    v1 = presc["version"]
    print("   prescription_id=", pid, "version=", v1, "status=", presc.get("status"))
    print("   exercises=", [e.get("name") for e in (presc.get("exercises") or [])])

    print("7) start session")
    ex = (presc.get("exercises") or [{"id": "squat", "name": "深蹲"}])[0]
    sess = c.post(
        "/sessions/start",
        json={
            "user_id": uid,
            "prescription_id": pid,
            "exercise_id": ex["id"],
            "exercise_name": ex.get("name", ex["id"]),
        },
    ).json()
    sid = sess["session"]["id"]
    print("   session_id=", sid)

    print("8) finish session → CoT + prescription bump")
    fin = c.post(
        f"/sessions/{sid}/finish",
        json={"video_path": "uploads/mock_session.mp4", "pose_summary": sess.get("pose_live") or {}},
    ).json()
    report = fin.get("report") or {}
    cot = report.get("cot") or {}
    new_p = fin.get("updated_prescription")
    print("   cot.score=", cot.get("score"), "errors=", cot.get("errors"))
    print("   cot.steps=", cot.get("steps"))
    if not new_p:
        print("FAIL: no updated_prescription")
        sys.exit(1)
    print("   new prescription version=", new_p.get("version"), "notes=", new_p.get("notes"))
    if int(new_p.get("version", 0)) != int(v1) + 1:
        print("FAIL: version not +1")
        sys.exit(1)

    print("9) fetch report by session")
    reps = c.get(f"/reports/{sid}").json()
    print("   ok keys=", list(reps.keys()) if isinstance(reps, dict) else type(reps))

    print("\nSMOKE OK — 假闭环跑通")


if __name__ == "__main__":
    main()
