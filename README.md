# Academic Paper Downloader

> ⚠️ **免责声明 (Disclaimer)** 
> 本项目仅供学术研究、个人学习以及技术交流使用。本项目旨在帮助科研人员在其合理合法的权限范围内（如公开获取的 Open Access 资源及个人合法订购的机构学术网络环境下）自动化建立个人的本地文献库。
> 
> * 开发者**不鼓励、不提供、也不承担**任何利用本工具进行恶意大规模批量抓取、绕过出版商安全防线、或建立盗版文献分发库所产生的任何法律纠纷和责任。
> * 工具本身不含有任何破解或鉴权绕过代码，获取成功率依赖于目标网站是否符合公开获取规范或用户的 IP 授权规范。
> * 请所有使用者严格遵守各大出版服务提供商（Elsevier、Springer、Wiley 等）及第三方 API（Unpaywall、OpenAlex）的《用户协议》与《隐私政策》，合理使用（Fair Use），切勿滥用引发 DDoS 或严重浪费公共网络资源。

---

**Academic Paper Downloader** 是一款本地跨平台运行的开源 CLI 工具。它可以通过命令行，基于关键词等跨越 PMC, PubMed, Crossref, OpenAlex 四大数据源进行检索聚合，并通过内置的 Unpaywall API 接口快速定位并合规获取其公开获取（OA）版本的 PDF 论文文献。

## ✨ 特性 (Features)

- **多数据源聚合检索**：整合 PMC, PubMed, Crossref, OpenAlex (2.5 亿+文献元数据记录) 进行交叉对比。
- **自动化 OA 发现**：内置集成 Unpaywall 开放 API，优先查找合法的最佳 Open Access (开放获取) 论文链接，降低人工筛查成本。
- **支持机构合规订阅访问**：支持在拥有出版商数据库合法订阅权限的机构 IP 环境下，依据合法匹配规则一键获取原文。
- **高性能、进度可视**：自带全自动化的断点续传系统缓存、多线程网络调度机制及美化的终端进度条 (`tqdm`)。
- **极简的 CLI 接口**：所有的参数可通过命令行注入，不侵入源码、不暴露用户隐私（如邮箱），执行完毕直接输出适配各类文献管理工具（如 Zotero、EndNote）的元数据表格 (`.csv`)。

## 🚀 快速开始 (Quick Start)

### 1. 安装依赖

请确保您的系统已安装 Python 3.8+。

```bash
# 克隆仓库
git clone https://github.com/WUWeifeng710/academic-paper-downloader.git
cd academic-paper-downloader

# 安装所有运行依赖
pip install -r requirements.txt
```

### 2. 命令行使用示例

```bash
# 检索并归档有关 "tomato disease resistance" 的公开文献
python -m paper_downloader.cli \
    --queries "(tomato) AND (disease resistance)" \
    --email your_email@domain.com \
    --outdir ./papers \
    --threads 5
```

> **注意**：您必须提供一个真实有效的个人或学术邮箱 (`--email`)，由于本项目重度依赖非营利开放组织接口 (Unpaywall、Crossref Polite Pool、OpenAlex)，合规传递邮箱是这些机构防止被恶意滥用并维持免费服务的前提。

## ⚙️ 核心参数说明

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `--queries` | 搜索关键词 (支持基础 Boolean 逻辑)。提供多个查词时用空格分隔（并在外层加引号使用）。 | ✅ | 无 |
| `--email` | API Polite Pool 验证邮箱（请勿使用 `@example.com` 否则可能遭到封禁处理）。 | ✅ | 无 |
| `--outdir` | PDF 下载结果和报告的保存目录路径。 | ❌ | `./papers` |
| `--threads` | 并发网络线程数，由于遵守 API rate limits，推荐值保持 3-10 内即可。 | ❌ | `5` |
| `--institutional` | 环境标识：当前运行网络环境是否拥有合法订阅的各大出版商机构库权限（通过 IP 校验等），声明为真则会依据部分出版商规则匹配链接。 | ❌ | `False` |
| `--retmax` | 每个查询词从单个源提取的最大论文条目限制。 | ❌ | `30` |

## 📃 产出结果

运行结束后，工具会在您的 `outdir` 下生成三种内容：
1. **下载完毕的 `.pdf` 原文** (提取通过校验的安全 PDF 文件名)。
2. **`download_report.txt`**：总结文本文档，展示本次运行的详情状态。
3. **`papers_metadata.csv`**：涵盖全部已成功匹配或识别到的文章核心字段（如 DOI、发布日期等），便于文献管理软件（如 Mendeley 等）录入归档。

## 🛡️ License

本项目采用 [MIT License](LICENSE) 授权。基于 "AS IS" (按原样提供) 原则提供使用，任何因违反其运行原理或用户私自用于其他用途导致的风险后果，本工具及原作者概不负责。
