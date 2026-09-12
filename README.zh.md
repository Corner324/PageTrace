<div align="center">

<img src="docs/assets/header.svg" alt="PageTrace" width="720">

[English](README.md) · [Русский](README.ru.md) · **中文**

**用你已经录下的轨迹，查清 API 分页到底做了什么。不访问网络。**

[![CI](https://github.com/Corner324/PageTrace/actions/workflows/ci.yml/badge.svg)](https://github.com/Corner324/PageTrace/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pagetrace.svg)](https://pypi.org/project/pagetrace/)
[![Coverage 98.97%](https://img.shields.io/badge/coverage-98.97%25%20branch-brightgreen.svg)](docs/testing.md)
[![Tests 425](https://img.shields.io/badge/tests-425-brightgreen.svg)](docs/testing.md)
[![Zero network](https://img.shields.io/badge/network-none-0aa344.svg)](docs/security.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](docs/compatibility.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[⚡ 安装](#-安装) · [🔍 工作原理](#-工作原理) · [🎯 预设](#-预设) · [🧭 它不会告诉你什么](#-它不会告诉你什么) · [🔒 安全](#-安全) · [📐 不变量](specs/invariants.md)

</div>

---

## 💡 为什么需要它

分页 bug 可以绕过你所有的健康检查。每一页都返回 `200 OK`，循环正常结束，日志里没有报错，
导出的数据却少了四百行。几周后有人核对总数，你才发现问题，而那时录制早就删掉了。

集成测试要调用线上 API，所以时好时坏。日志把每个请求记成单独一行，bug 却出在两行之间：
第 3 页发出的令牌，第 2 页从来没有返回过。你可以自己读 HAR 找出这种问题，但轨迹超过十来页
就读不过来了。

PageTrace 读取你手上已有的录制，报告能从中证明什么。

| 你听到的说法 | PageTrace 能从轨迹里告诉你什么 |
| ------------ | ------------------------------ |
| "导出的数据少了几行" | 是否有一页用了上一页没有返回过的令牌；请求序列是否回到了之前的状态；录制是否提前停止 |
| "任务一直跑不完" | 游标是否卡在同一个值上，或者请求是否回到了已经去过的状态 |
| "下游收到了重复数据" | 哪个条目身份出现在了哪两页上 |
| "是他们的 API 坏了" | 轨迹能否支持把责任归给任何一方（很多时候不能） |

> [!IMPORTANT]
> **规则：PageTrace 绝不宣称超出轨迹所能证明的内容。**
> 每条发现都会给出确定性，并列出它依据的观测。工具里没有置信度分数。如果轨迹缺少某项检查
> 需要的证据，你会得到 `INSUFFICIENT_EVIDENCE`，以及需要设置的命令行标志名称。

常见用法有两种：在 CI 的回归测试里，已证明的缺陷让构建失败；或者在线上事故中，同事导出的
HAR 是唯一剩下的证据。接入供应商的 API 之前，它也能派上用场，你可以把不夸大的发现直接发给对方。

---

## ⚡ 三十秒看明白

```bash
uv run pagetrace check examples/broken-cursor.jsonl
```

```
broken-cursor.jsonl: 3 pages, preset cursor

PROVEN ERROR CURSOR_CONTINUATION_MISMATCH [INV-CURSOR-001] pages 1, 2
  Page 2 was requested with a continuation token that page 1 did not return.
  page[1].response.next_cursor = "eyJvIjo0fQ"
  page[2].request.cursor = "eyJvIjozfQ"

PROVEN WARNING DUPLICATE_ITEM_ACROSS_PAGES [INV-ITEM-001] pages 1, 2
  An item observed on page 1 was observed again on page 2; its identity is in the evidence below. That the same item appears twice is a fact; whether it means overlapping pages depends on a uniqueness contract this trace does not contain.
  page[1].items[0].id = 3
  page[2].items[0].id = 3

2 proven, 0 suspicious, 0 insufficient evidence
```

命令以退出码 1 结束。第二条发现报告了一个重复条目，到此为止。轨迹里没有唯一性契约，所以
PageTrace 不把这个重复称为分页 bug。

`examples/clean-cursor.jsonl` 是同一次运行去掉缺陷后的版本，退出码为 0。

---

## 🔍 工作原理

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/flow.zh.dark.svg">
  <img alt="已录制的轨迹、解析器、规范化、不变量引擎、报告。任何一步都不发起网络请求。" src="docs/assets/flow.zh.light.svg" width="820">
</picture>
</div>

检测器只接收规范化后的观测。`Page` 没有存放原始响应体或 `authorization` 头的字段，所以引擎
没有办法读到它们。模块结构见 [docs/architecture.md](docs/architecture.md)。

---

## ⚡ 安装

```bash
pip install pagetrace
```

`pipx install pagetrace` 和 `uv tool install pagetrace` 会把它装成独立命令。

要运行示例，请克隆仓库并使用 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync
uv run pagetrace check examples/broken-cursor.jsonl
```

---

## 📼 如何录制轨迹

JSONL 轨迹里，每一对请求和响应占一行 JSON 对象，按录制顺序排列：

```json
{"v": 1, "seq": 0, "request": {"method": "GET", "url": "https://api.example.com/v1/items?limit=2"}, "response": {"status": 200, "headers": {"content-type": "application/json"}, "body": {"items": [{"id": 1, "name": "item-1"}, {"id": 2, "name": "item-2"}], "next_cursor": "eyJvIjoyfQ", "has_more": true, "total": 5}}}
```

`v` 和 `response.status` 必填。`seq` 可以省略，PageTrace 以行的顺序为准。完整规则见
[specs/formats/jsonl-v1.md](specs/formats/jsonl-v1.md)。

<details>
<summary><b>或者从浏览器导出 HAR</b>，适用于任何能在浏览器里打开的 API</summary>

<br>

在 DevTools 里打开 Network 标签页，把结果一页页翻完，再把请求列表保存为 HAR。文件里还会有
页面加载的脚本、图片和字体，所以要先筛出 API 调用：

```bash
uv run pagetrace check your-capture.har --url-filter /v1/items
```

PageTrace 在给页面编号之前会丢掉 `OPTIONS` 和 `HEAD` 请求，因此 CORS 预检请求不会被当成
卡在同一页的客户端。

</details>

> [!WARNING]
> HAR 文件里有仍然有效的凭据。PageTrace 只保留一个响应头，也从不打印响应体，但你磁盘上的文件
> 依旧包含 `Authorization` 头。请像保管密码一样保管它，不要附到公开的 issue 里。

---

## 🎯 预设

选择器使用 [RFC 9535](https://www.rfc-editor.org/rfc/rfc9535.html) 的 JSONPath。如果预设默认值
什么都没匹配到，PageTrace 会把该值记为未找到，不据此得出任何结论。

| 预设 | 默认选择器 | 适用于 |
| ---- | ---------- | ------ |
| `cursor` <sub>默认</sub> | `--cursor $.query.cursor` `--next $.next_cursor` `--items $.items` `--id $.id` `--total $.total` `--has-more $.has_more` | 返回不透明续传令牌的 API |
| `page` | `--page $.query.page`，以及同样的 items / id / total / has-more | 页码，从 0 或从 1 开始 |
| `offset` | `--offset $.query.offset`，以及同样的 items / id / total / has-more | offset 与 limit |
| `link` | 只有 items / id / total / has-more；下一页来自 HTTP `Link` 头 | Link 头中的 `rel="next"`（RFC 8288） |

> [!TIP]
> 每个默认值都能用对应的标志覆盖。`uv run pagetrace check --help` 按预设列出默认值。发现为
> `INSUFFICIENT_EVIDENCE` 时，消息里会写明需要设置的标志。

---

## 📊 确定性、严重度、退出码

每条发现有两个彼此独立的评级。确定性说明轨迹对它的支持程度，严重度说明它若成立有多重要。
两者都不是概率。

| 确定性 | 含义 |
| ------ | ---- |
| `PROVEN` | 轨迹显示了这一点，且前置条件成立 |
| `SUSPICIOUS` | 轨迹符合缺陷，也符合某种无害的解释 |
| `INSUFFICIENT_EVIDENCE` | 选择器或轨迹没有提供检查所需的内容 |

| 退出码 | 含义 |
| ------ | ---- |
| `0` | 没有既被证明又严重的发现 |
| `1` | 至少有一条 `PROVEN` 发现的严重度为 `ERROR` |
| `2` | 输入或配置无效 |

退出码 1 需要两个评级同时满足。跨页重复条目是 `PROVEN WARNING`，不会让构建失败。这条发现没有
把重复称为 bug，而失败的构建等于替它下了这个结论。如果构建因为可能只是缓存造成的现象而变红，
团队就会开始无视这个工具。

在 CI 里请读取 JSON 输出。PageTrace 不保证终端输出格式保持稳定：

```bash
uv run pagetrace check examples/broken-cursor.jsonl --format json --output report.json
```

---

## 🧭 它不会告诉你什么

下面这些问题 PageTrace 不回答，即使轨迹看起来指向了某个答案。

- 分页是否会终止。有限的轨迹能显示请求序列回到了之前的状态，`INV-CURSOR-003` 报告的就是这一点。
  如果在 `null` 游标之后回到第 0 页的状态，这条发现会降为 `SUSPICIOUS`：存进同一个文件的两次
  运行看起来是一样的。
- 记录是否丢失。`INV-TOTAL-001` 把声明的总数和观测到的条目身份作比较，消息里不会出现"丢了 N 条
  记录"。PageTrace 无法知道 `total` 统计的是否是同一批条目、录制期间数据有没有变化、两边是否用了
  相同的过滤条件。
- 谁有责任。`INV-CONT-001` 和 `INV-TRACE-001` 报告的是：服务端还在提供后续页面时，轨迹就结束了。
  它们不指责 API，不指责客户端，也不指责录制的人。
- 重复条目意味着什么。发现只报告重复本身。要把它叫作 bug，需要一份唯一性契约，而轨迹里没有。
- 基于读不了的页面的任何结论。读取响应体的检查会跳过非 2xx 响应，`INV-TRACE-002` 会把跳过的
  请求报告一次，所以全是错误的轨迹不会被当成干净的。
- 基于没有解析成功的选择器的任何结论。选择器什么都没匹配到、匹配到两个值或指向一个对象时，
  结果是 `INSUFFICIENT_EVIDENCE`，并写明对应的标志。JSON `null` 算作一次观测：服务端表示没有下一页。
- `5` 和 `"5"` 是否不同。PageTrace 按文本比较值，因为查询参数只能携带文本。它也不会把 `1` 或
  `"true"` 当作 `has_more`，只有 JSON 布尔值才算。

[specs/invariants.md](specs/invariants.md) 列出了全部十一条不变量的宣称内容，以及每个检测器保持
沉默的条件。工具把这个文件当作契约来遵守。

---

## 🔒 安全

请把 HAR 或 JSONL 轨迹当作含有机密的不可信输入。解析器只保留一个响应头 `link`，因为 link
预设会读取它。`authorization`、`cookie` 和其他头会在构建模型之前被丢弃。检测器和渲染器拿不到
原始响应体，所以报告里只有你选中的值，控制字符会被转义，过长的值会被截断。PageTrace 限制单行
长度和解码后的响应体大小，超限输入按使用错误处理，退出码为 2，并且不包含任何网络代码或
网络依赖。威胁表和各项限制见 [docs/security.md](docs/security.md)。

---

## 📈 性能

测量时间 2026-09-11，机器为 Windows 11 开发机，CPython 3.12.6，每种形状跑一次。内存指
`tracemalloc` 报告的 Python 峰值分配量。再跑一次最后一位数字会变，所以请看比例。

| 形状 | 页数 | 条目数 | 秒 | 峰值 MiB |
| ---- | ---: | -----: | -: | -------: |
| 宽 | 1 000 | 100 000 | 2.6 | 16.1 |
| 很宽 | 1 000 | 1 000 000 | 20.9 | 156.8 |
| 一万页 | 10 000 | 1 000 000 | 28.3 | 142.8 |
| 十万页 | 100 000 | 5 000 000 | 120.8 | 715.4 |

> [!NOTE]
> PageTrace 有三项时间目标没有达到，项目仍把它们保留为目标。1k 页 / 100k id 应在 2 秒内完成，
> 实测 2.6 秒。10k / 1M 应在 10 秒内完成，实测 28.3 秒，约为三倍。100k / 5M 的延伸目标是 60 秒，
> 实测 120.8 秒，约为两倍。峰值内存在两项上限之内：142.8 MiB 对 512 MiB，715.4 MiB 对 2 GiB。
> 完整表格和分析见 [docs/performance.md](docs/performance.md)。

---

## 🛠 参与开发

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

全部 425 个测试在本地通过，分支覆盖率 98.97%，环境为 Windows 上的 Python 3.11、3.12、3.13 和
3.14。`tests/property/` 里的性质测试承担了大部分正确性检查：任何生成的有效轨迹都不能产生
`PROVEN` 发现，每个变异算子必须恰好触发一个检测器。2026-09-12 针对单元测试的变异得分是 77.9%，
[docs/testing.md](docs/testing.md) 对存活的变异体做了人工分类。mutmut 不能在 Windows 上运行，
所以那次运行用的是 Linux 容器。

新检测器先在 [specs/invariants.md](specs/invariants.md) 里写一条条目，列出它保持沉默的条件，
然后写测试预言，最后写代码。[CONTRIBUTING.md](CONTRIBUTING.md) 说明流程和完成标准，
[AGENTS.md](AGENTS.md) 给编码智能体提供同样的规则。更多内容见
[docs/architecture.md](docs/architecture.md)、[docs/testing.md](docs/testing.md)、
[docs/compatibility.md](docs/compatibility.md)、[docs/adr/](docs/adr/) 和
[CHANGELOG.md](CHANGELOG.md)。

<div align="center">

**MIT** · [LICENSE](LICENSE)

</div>
