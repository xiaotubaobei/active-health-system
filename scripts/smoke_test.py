"""API 冒烟：新用户首次测评 → 模板处方 → 训练归档 → 重试 → 历史。

使用独立测试账号，不修改 demo 用户的档案。AI 服务可不启动；
演示 / 备用分数不计入模型成绩，训练结束不自动调整处方。
"""
from uuid import uuid4

import httpx

API = "http://127.0.0.1:8000"


def main():
    with httpx.Client(base_url=API, timeout=30.0) as client:
        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        print("1) check API /health")
        print("   ", request("GET", "/health"))

        print("2) register a dedicated smoke-test account")
        created = request("POST", "/auth/register", json={
            "username": f"smoke-{uuid4().hex[:12]}",
            "password": uuid4().hex, "privacy_consent": True,
        })
        uid = created["user"]["id"]
        print("   user_id=", uid)

        print("3) complete first assessment with all scale items")
        scales = request("GET", "/fitness/scales")
        scale = next(s for s in scales if s["id"] == "middle_elder")
        onboard = request("POST", "/onboarding/complete", json={
            "user_id": uid, "age_group": "middle_age",
            "height_cm": 170, "weight_kg": 65, "goal": "fitness",
            "privacy_consent": True, "scale_id": scale["id"],
            "scores": {item["key"]: 70 for item in scale["items"]},
        })
        presc = onboard["prescription"]
        assert onboard["baseline"]["total_score"] == 70
        assert presc["version"] == 1

        print("4) start session")
        started = request("POST", "/sessions/start", json={
            "user_id": uid, "prescription_id": presc["id"],
            "exercise_id": "squat", "exercise_name": "深蹲",
        })
        sid = started["session"]["id"]

        print("5) finish and retry: one report, one archive, no prescription change")
        body = {"video_path": "", "pose_summary": {"source": "smoke_test"}}
        finished = request("POST", f"/sessions/{sid}/finish", json=body)
        retried = request("POST", f"/sessions/{sid}/finish", json=body)
        assert finished["report"]["id"] == retried["report"]["id"]
        assert finished["kb_entry_id"] == retried["kb_entry_id"]
        assert finished["updated_prescription"] is None
        if finished["analysis"]["status"] != "model":
            assert finished["analysis"]["score"] is None
        current = request("GET", "/prescriptions/current", params={"user_id": uid})
        assert current["id"] == presc["id"] and current["version"] == 1

        print("6) read report and history")
        report = request("GET", f"/reports/{sid}")
        summary = request("GET", f"/users/{uid}/kb/summary")
        sessions = request("GET", f"/users/{uid}/sessions")
        assert report["report"]["id"] == finished["report"]["id"]
        assert summary["kb_entries"] == summary["finished_sessions"] == len(sessions) == 1
        if finished["analysis"]["status"] != "model":
            assert summary["avg_score_recent"] is None
        print("   session_id=", sid, "analysis=", finished["analysis"]["status"])
        print("\nSMOKE OK — 注册、测评、训练归档与历史查询通过；未验证真实算法。")


if __name__ == "__main__":
    main()
