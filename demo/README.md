# Civil Buddy 工作台 Demo（WorkBuddy 用法）

- **不召唤专家**：普通对话（你配置的模型），无知识库、无出稿工具。
- **召唤专家**：该专家独立走完「理解 → 检索私库+大类共享库 → 成稿 → 自检」，像易标的一个模块。
- **一类专家共享** `kb/<大类>/_shared/`，**每个专家另有私库** `kb/<大类>/<专家id>/`，公司规则在 `kb/company/`。

## 启动

```powershell
cd C:\Users\LW\civil-buddy\demo
copy .env.example .env
# 编辑 .env，填入 CIVIL_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY（自选模型，不必 DeepSeek）
python -m pip install -r requirements.txt
python serve.py            # 读 .env 里的 CIVIL_HOST / CIVIL_PORT；等价于 uvicorn app:app --host 127.0.0.1 --port 8765
```

浏览器打开 http://127.0.0.1:8765

### 手机 / 局域网

1. `.env` 里加 `CIVIL_HOST=0.0.0.0`，再加 `CIVIL_TOKEN=随便一串`（工作室能读写这台电脑的知识库，开给局域网就得有口令）。手机第一次打开会弹一次口令输入，之后存在 cookie 里，下载链接和上传都自动带；脚本用 `Authorization: Bearer <口令>`。没设口令就开到 0.0.0.0，`serve.py` 会在启动时警告。
2. 手机同一 Wi-Fi 打开 `http://<电脑IP>:8765`。窄屏时侧栏变成顶栏「栏目」按钮拉出的抽屉；弹出键盘时输入框保持在键盘之上。
3. 成稿期间锁屏 / 切后台 / 断网回来：服务端继续跑完（`CIVIL_DETACHED_TURN_SECONDS`，默认 600 s 内），页面回来后从 `GET /api/sessions/{sid}` 拉回结果。只有点「停止」才真的取消。
4. 模型慢：`CIVIL_LLM_READ_TIMEOUT`（两段输出之间最长等多久，默认 180 s）、`CIVIL_LLM_CONNECT_TIMEOUT`（默认 15 s）。

高风险专家（施工方案、危大、交底、结构）写盘前勾选确认句。

经营投标三岗与装箱主线共用 `packing_assistant.tools.tender_parse`：

- 招标解析 → `extract_tender`（评分点 / ★ / 工期只抄原文）
- 废标检查 → `compliance_gaps`（P0 须人确认，不判定可投标）
- 技术标 → `tech_expand`（按抽出评分点出目录，不套上个项目模板）

## 自己设计专家和知识库

点右上角 **设计专家 / 知识库**：

- 新建大类、新建专家（id、职责、风险、别名）
- 打开任意一篇私库 / 大类共享 / 公司库，直接改 Markdown
- 每篇显示字节数和字数；专家私库合计超软上限会标红
- 可改软上限（默认 200 KB/专家）；单文件硬顶 512 KB
- 自定义专家可连私库一起删；内置专家只能从召唤墙隐藏

用户改动落在 `demo/kb/` 与 `demo/data/user_catalog.json`。

## 演示建议

1. 不点专家，问「栏杆一般多高」→ 普通闲聊，会声明不是专家稿。
2. 点「危大识别」，问临边要不要论证。
3. 勾选确认后点「施工方案」，出 11 章讨论提纲。
4. 再点「工友白话」，同一任务出口播稿。
5. 右侧应出现 **私库 / 大类 / 公司** 三层引用。
