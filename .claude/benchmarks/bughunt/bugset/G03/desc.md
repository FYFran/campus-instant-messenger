# G03 — G2: Silent External Model Degradation

## Bug 描述

火眼在外部模型不可用时会 fallback 到本地模型。但这个 fallback 没有被正确标注——报告中不显示实际使用的模型，导致用户无法区分"用 GPT/Claude 分析的结果"和"用本地小模型分析的结果"。

检查火眼的模型选择逻辑和输出标注。证明存在静默降级——外部模型调用失败时，输出没有标记 `Mode: single`，用户以为得到了高质量分析。
