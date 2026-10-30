import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _stub import make_app, VisualEncIn

app = make_app("visual_encoder")


@app.post("/encode")
def encode(body: VisualEncIn):
    return {
        "visual_sentence": ["frame_tok_1", "frame_tok_2", "EOS"],
        "encoders": ["CLIP-ViT", "CLIP-ConvNeXt", "DINOv2-ViT"],
        "embedding_dim": 768,
        "video_path": body.video_path,
        "mode": "mock",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8105)
