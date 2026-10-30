# 展示前 1 小时清单

## 0–10 分钟：服务全开

三个窗口保持开着（不要关）：

```powershell
# 1) RTMPose
cd ai_services\pose
$env:RTMPOSE_MODE="lightweight"
$env:RTMPOSE_BACKEND="onnxruntime"
python main.py

# 2) 后端
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 3) 前端
cd frontend
npm run dev
```

自检：

- http://127.0.0.1:5173 能开页  
- http://127.0.0.1:8000/health  
- http://127.0.0.1:8000/pose/estimator 能看到 `rtmpose_...`

## 10–25 分钟：演练主线（只练这一条）

1. 登录 `demo` / `123456`  
2. **运动中监测** → 离线视频  
3. 演示样本优先下拉里带 **★推荐** 的：`repcount_stu4_66`（多重复）；备选 `stu1_68` / InfiniteRep `000000`  
   口述稿见 `docs/demo_talk_script.md`。  

4. 等「RTMPose 完成」→ **播放**看骨架跟着动  
5. **开始会话** → **结束并生成报告**  
6. 报告页看分数/CoT；点「查看已更新处方」提一句闭环  

口头一句：  
「姿态是服务端 RTMPose 真算的 COCO-17；报告里的 CoT 文字目前是可替换桩，结构已通。」

## 25–40 分钟：排雷

- 不要现场乱点半身/模糊视频  
- 解析失败：看是否 8101 挂了，重启 pose  
- 报告 404：必须先「结束会话」再进报告  
- 浏览器挡播放：点视频条上的播放键  

## 40–60 分钟：冷静 / 备用

- 可选：总览「一键跑通演示闭环」当开场 30 秒  
- 可选：摄像头骨架 20 秒加分（有时间再开）  
- 手机热点备用；别临时改代码  

## 别碰

Fitness-AQA、换大模型、重构、3D。
