# Spark 开发流 · 动画讲解

纸面手绘风的项目讲解动画，约 4 分半，11 章，阶跃 TTS 配音。画面完全由时间决定：配音是主时钟，拖进度条、倍速、跳章都不会错位；也能逐帧导出成视频，直接当演示视频的素材。

```bash
npm install
npm run dev            # http://localhost:5180
npm run tts            # 改了 src/script.json 的台词后重新生成配音（只重做改过的句子）
npm run build && npm run preview
```

- 台词：`src/script.json`。画面按「第几句开始后多少秒」安排，改台词、换音色后重新 `npm run tts`，动画自动跟上新节奏。
- 换音色：`VOICE=cixingnansheng npm run tts`（实测可用：zhixingjiejie、wenrounvsheng、wenjingxuejie、cixingnansheng、wenrounansheng 等 12 个）。
- 密钥：只从环境变量 `STEPFUN_API_KEY` 或仓库根 `.env` 读，不会进任何产物。逐句音频缓存在 `.tts-cache/`（不入库）。
- 播放器：空格 暂停，← → 切章，C 开关字幕；`?clean` 隐藏控件（录屏），`#gate` 直接跳到某一章。

## 导出

```bash
npm run build && npm run preview                       # 另开终端
node scripts/capture.mjs scenes out/                  # 每章两帧，自检用
node scripts/capture.mjs stills out/ 12.5,61,130      # 指定时间点
node scripts/capture.mjs video out/explainer.mp4 30   # 逐帧导出 + 合配音（需要 ffmpeg）
```

## 结构

```
src/engine/ink.ts       墨线引擎：折线 → 手抖 → 按进度写出；方框、箭头、荧光笔、印章、便利贴、条形
src/engine/paper.ts     程序化纸张
src/engine/timeline.ts  配音时间线：每句的起止时间 → 场景里的进度函数
src/scenes/part*.ts     11 章画面
scripts/tts.mjs         逐句 TTS → 拼接成一条配音 + manifest.json
scripts/capture.mjs     无头 Edge 截帧 / 导出视频
```

字体：霞鹜文楷（LXGW WenKai，SIL OFL 1.1）。
