import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _stub import make_app, ParsingIn

app = make_app("parsing")


@app.post("/analyze")
def analyze(body: ParsingIn):
    return {
        "parts": ["torso", "left_leg", "right_leg", "left_arm", "right_arm"],
        "ratios": {"torso": 0.32, "legs": 0.48, "arms": 0.20},
        "clicks_applied": body.clicks,
        "text_prompt": body.text_prompt,
        "open_set": True,
        "mode": "mock",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8104)
