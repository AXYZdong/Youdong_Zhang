# Youdong Zhang · 个人学术主页

本项目采用 `template/acad-homepage.github.io` 的 **Jekyll 文件结构**。个人资料用 YAML 配置，正文用 Markdown 编辑，布局和样式单独维护。

最终发布使用 GitHub Pages 的 Jekyll 构建。当前按已有仓库 `AXYZdong/Youdong_Zhang` 配置，部署后地址为 `https://axyzdong.github.io/Youdong_Zhang/`；发布步骤及根主页配置见下方“GitHub Pages 发布”。

## 日常只需编辑这些文件

| 想修改的内容 | 对应文件 |
| --- | --- |
| 姓名、头像路径、学校、邮件、学术平台、站点标题和更新日期 | `_config.yml` |
| 简介、研究兴趣、论文及报告、教育经历、Contact 正文 | `_pages/about.md` |
| 顶部导航标题与锚点 | `_data/navigation.yml` |
| 个人照片和网站图标 | `images/profile.jpg`、`images/favicon.svg` |
| 自定义颜色、间距、字号或手机布局 | `_sass/_custom.scss` |
| 下载的参考文献 | `files/publications.bib` |

`_pages/about.md` 中使用普通 Markdown：`#` 是分区标题，`##` 是年份标题，`- ` 是论文或经历条目，`**文字**` 是加粗，`[显示文字](网址)` 是链接。新增论文时复制一个相邻条目，更新内容即可；如果希望 BibTeX 下载同步更新，再修改 `files/publications.bib`。

页首的 `---` 区域是 Jekyll 配置，请保留 `permalink: /` 和 `author_profile: true`。四个 `<span class='anchor' id='...'></span>` 是导航定位点，修改 ID 时也要同步修改 `_data/navigation.yml`。

联系邮箱和学术平台在正文中引用 `site.author` 配置；更新 `_config.yml` 后，侧栏与 Contact 会同步变化。GitHub 填写用户名，Google Scholar、ResearchGate 和 ORCID 填写完整网址。

## 目录结构

```text
Youdong_Zhang/
├── _config.yml                # 个人资料与站点配置
├── _data/
│   └── navigation.yml         # 顶部导航
├── _pages/
│   └── about.md               # 主页正文，日常主要编辑此文件
├── _layouts/
│   └── default.html           # 页面框架
├── _includes/                 # 头像侧栏、导航、head、footer 等组件
├── _sass/
│   ├── _variables.scss        # 模板变量
│   ├── _custom.scss           # 个人样式调整
│   └── ...                    # 原模板样式和 vendor
├── assets/
│   ├── css/main.scss          # 样式入口，自动编译为 main.css
│   ├── js/_main.js            # 可直接编辑的导航脚本
│   └── fonts/                 # 模板的本地图标字体
├── images/                    # 头像与网站图标
├── files/publications.bib     # 可下载参考文献
├── Gemfile                    # 正式 Jekyll 构建依赖
├── .github/workflows/
│   └── jekyll-build.yml        # GitHub 上的正式构建检查
├── run_server.sh              # Jekyll 本地预览
├── run_server.ps1             # Windows 本地预览
└── tools/preview.py           # 未安装 Ruby 时的可选预览
```

`_site/` 是自动生成的页面，`.preview/` 是本地截图和旧版文件备份，两者均被 Git 忽略。无需编辑这些目录中的 HTML，也无需手工维护根目录 `index.html`。

## 本地预览

在本目录打开终端，运行：

```powershell
python tools/preview.py
```

打开 [http://127.0.0.1:8765/Youdong_Zhang/](http://127.0.0.1:8765/Youdong_Zhang/)。访问端口根地址也会自动跳转。保存 Markdown、YAML、HTML 组件或 SCSS 后，预览会自动更新。按 `Ctrl+C` 停止预览。

只生成页面：

```powershell
python tools/preview.py --build
```

本机的预览依赖已限定安装在 `tools/.deps/`。在另一台只有 Python 的电脑上可安装到相同目录：

```powershell
python -m pip install --target tools/.deps --cache-dir tools/.cache -r tools/requirements-preview.txt
```

Python 预览使用 Liquid 模板、Markdown 和真实 Sass 编译，读取的就是上述 Jekyll 源文件；它只预览本项目的静态页面，不实现全部 Jekyll 插件。正式 Jekyll 使用 Kramdown，复杂 Markdown 和插件扩展应以正式构建结果为准。

如果已经安装 Ruby 和 Bundler，可使用标准 Jekyll：

```powershell
bundle config set --local path vendor/bundle
bundle install
bundle exec jekyll serve --livereload --host 127.0.0.1
```

Jekyll 默认端口为 4000，当前项目预览地址为 `http://127.0.0.1:4000/Youdong_Zhang/`。修改 `_config.yml` 后需重启 Jekyll。脚本 `run_server.ps1` 会优先使用 Jekyll，未安装时启动 Python 预览。

## GitHub Pages 发布

### 1. 确定仓库和地址

| 部署方式 | GitHub 仓库 | 公开地址 | `_config.yml` 中的 `baseurl` |
| --- | --- | --- | --- |
| 当前项目主页 | `AXYZdong/Youdong_Zhang` | `https://axyzdong.github.io/Youdong_Zhang/` | `"/Youdong_Zhang"` |
| 用户根主页 | `AXYZdong/AXYZdong.github.io` | `https://axyzdong.github.io/` | `""` |

当前配置已经对应第一行：

```yaml
url: "https://axyzdong.github.io"
baseurl: "/Youdong_Zhang"
repository: "AXYZdong/Youdong_Zhang"
```

如果希望网址直接是 `https://axyzdong.github.io/`，先在 GitHub 创建或使用名为 `AXYZdong.github.io` 的仓库，然后将配置改为：

```yaml
url: "https://axyzdong.github.io"
baseurl: ""
repository: "AXYZdong/AXYZdong.github.io"
```

`url` 只填写域名，仓库路径写在 `baseurl`。头像、样式、脚本、下载文件、导航和 canonical 地址均通过 Jekyll 的 URL 过滤器生成，支持以上两种地址。修改配置后，本地预览路径也会相应变化。

### 2. 把源码放到仓库根目录

仓库根目录应直接出现 `_config.yml`、`_pages/`、`_includes/`、`_layouts/`、`_data/`、`_sass/`、`assets/`、`images/`、`files/`、`Gemfile` 和 `.github/`。上传的是 **`Youdong_Zhang` 文件夹内的内容**，不要在仓库内再嵌套一层 `myhomepage/Youdong_Zhang/`。

使用 Git 提交时，`.gitignore` 会排除 `_site/`、`.preview/`、`tools/.deps/`、缓存和 Ruby 的 `vendor/`。保留 `_sass/vendor/`，它是模板样式的组成部分。使用网页上传时也请主动跳过这些生成、备份和依赖目录。

当前本地分支是 `main`，远程仓库已指向 `AXYZdong/Youdong_Zhang`。确认发布到这个仓库后，可在本目录自行运行：

```powershell
git status
git add .
git commit -m "Add academic homepage"
git push -u origin main
```

如果改用用户根主页仓库，请先确认该仓库已创建，再将本地 `origin` 改为该仓库地址后提交和推送。

### 3. 启用 GitHub Pages

1. 在 GitHub 打开目标仓库的 **Settings → Pages**。
2. 在 **Build and deployment → Source** 中选择 **Deploy from a branch**。
3. 选择包含源码的分支（当前为 `main`）和 **`/(root)`**，点击 **Save**。
4. 等待 GitHub 的 **pages build and deployment** 成功，再打开上表中的公开地址。

保持 Jekyll 源码发布方式：根目录不添加 `.nojekyll`；首页由 `_pages/about.md` 的 `permalink: /` 生成，不需要另写根目录 `index.html`。`_site/` 是本地生成目录，GitHub 会自行从源码构建。Python 预览工具只用于本地查看，线上无需安装或运行 Python。

### 4. 核对正式构建

`.github/workflows/jekyll-build.yml` 在推送、Pull Request 或手动运行时，用 `github-pages` 依赖执行正式 Ruby/Jekyll 安全构建，并检查首页、样式、脚本、头像、站点地图及重定向页。可在仓库的 **Actions → Jekyll build check** 中查看结果；也可以选择 **Run workflow** 手动运行。

该工作流仅进行构建校验，发布由上一步配置的 GitHub Pages 流程负责。本机目前没有 Ruby/Bundler，因此本地已验证的 Python 预览不能代替正式构建结果；推送后请确认构建检查与 Pages 发布均成功。当前未替你提交、推送或发布。

官方说明：[使用 Jekyll 创建 GitHub Pages 站点](https://docs.github.com/en/pages/setting-up-a-github-pages-site-with-jekyll/creating-a-github-pages-site-with-jekyll)。

## 内容与来源

个人信息来自 `myhomepage/asset/my profile.md`，照片来自原始资料。6 条成果保留原始作者顺序和 Accepted / Early Access 状态，LBS 2026 条目标为会议报告；暂未放论文图。

模板与原始资料均未修改。模板许可见 `LICENSE`，第三方字体和样式归属见 `THIRD_PARTY_NOTICES.md`。上一版静态页面保存在 `.preview/previous-static/`，不参与构建和发布。
