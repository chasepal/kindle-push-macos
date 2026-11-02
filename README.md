<p align="center"><img src="mac-app/Assets/AppIcon-source.png" width="144" alt="Kindle 推送图标"></p>

<h1 align="center">Kindle 推送 · macOS</h1>

<p align="center">把 Markdown 变成适合阅读的 EPUB，通过 Wi-Fi 发到 Kindle。</p>

<p align="center"><a href="https://github.com/chasepal/kindle-push-macos/releases/latest">下载 v1.1.0</a> · <a href="docs/SETUP.md">首次配置</a> · <a href="docs/FORMATS.md">格式支持</a> · <a href="docs/TROUBLESHOOTING.md">常见问题</a></p>

看了乔木的 Kindle / KOReader 分享后，做了这个 Mac 端配套小工具。文章在 Obsidian 或本地文件夹里写好，拖进应用、点发送，就能拿到 Kindle 上慢慢读。不用每次打开终端或 AI，也不需要云端中转。

这是一个独立项目，感谢 [乔木 SimpleUI](https://github.com/joeseesun/qiaomu-simpleui) 的启发。它通过 KOReader 的 SSH 服务传文件，**不要求安装 SimpleUI，也不包含越狱工具**。

## 能做什么

- **Markdown → EPUB**：保留标题、作者、目录、列表、表格、代码和脚注，加入适合小屏阅读的样式。
- **Obsidian 支持**：双链转为显示文字，图片打包到 EPUB，支持整篇笔记嵌入和提示块。
- **拖放与批量发送**：支持 `.md`、`.markdown`、`.epub`，记录发送结果，失败可重试。
- **换 Wi-Fi 后寻找设备**：先尝试上次地址，再寻找已配对的 Kindle；也可手动填写 IP。
- **发送后校验**：读回远端 EPUB，比较 SHA-256，确认传输一致。
- **原文不改动**：只读选择的文章及其引用附件，转换副本保存在本机。

## 使用条件

| 项目 | 要求 |
| --- | --- |
| Mac | macOS 14 或更新；提供 Apple Silicon / arm64 预编译包 |
| 转换组件 | Homebrew Python 3.10+、Pandoc 3.8+（推荐安装当前版） |
| Kindle | 已越狱、已经安装并运行过 KOReader，包含 SSH / Dropbear 插件 |
| 网络 | Mac 和 Kindle 在同一个可互通局域网，Kindle 开启 Wi-Fi、运行 KOReader |
| 首次配置 | 插一次 USB 写入接收配置，再配对设备身份；完成后日常只用应用 |

实机测试设备：Kindle Paperwhite 3 / 第七代，固件 5.16.2.1.1，KOReader v2026.07.1。其他型号、旧版 KOReader 和 Intel Mac 尚未实机验证。

## 开始使用

1. 安装转换组件：`brew install python pandoc`。
2. 从 [Releases](https://github.com/chasepal/kindle-push-macos/releases/latest) 下载应用 ZIP，解压后放入“应用程序”。
3. 按 [首次配置](docs/SETUP.md) 完成 USB 接收端安装与设备配对。发布包不包含任何人的密钥，不能跳过这一步。
4. 打开 **Kindle 推送**，拖入文章，点 **发送到 Kindle**。
5. 在 KOReader 文件浏览器进入 `documents/我的文章` 阅读。

应用目前使用本地 ad-hoc 签名，没有 Apple Developer ID 公证。macOS 可能提示无法验证开发者；是否打开由你自行决定，也可以从源码构建。不会要求全局关闭 Gatekeeper。

## 换网络也能用吗？

可以：两台设备换到同一个新 Wi-Fi 后，应用会尝试重新发现设备，设备身份不随 IP 改变。常见家庭 /24 网络可自动扫描；更大的网络可手动输入 IP。访客网络隔离、不同 Wi-Fi、互联网远程推送不在支持范围内。

换网恢复的逻辑已通过自动化测试，当前局域网的主动发现已实机测试；没有把“实际切换了多个路由器”当作已完成测试。

## 格式转换能还原到什么程度？

常见文章排版已覆盖，目标是适合墨水屏的可重排阅读，**并非像素级复制 Obsidian 界面**。

图片找不到、嵌入循环或附件重名时会明确停止。Mermaid / Dataview 保留为代码并提示，不会自动执行。按标题/块嵌入、复杂公式与特殊 HTML 的限制见 [格式支持表](docs/FORMATS.md)。

## 隐私与连接

- 不上传文章到任何云服务，不提供遥测或后台同步。
- 如果文章包含远程图片，Pandoc 可能访问该图片地址下载素材；需要完全离线时请先把图片存到本地。
- 专用 SSH 私钥仅在本机生成和保存；Kindle 保存公钥。
- 首次配对明确确认设备身份；后续严格核对已固定的主机密钥。
- 专用接收密钥仅能调用收发协议，禁用任意命令、终端和端口转发。
- 不自动扫描或导入整个 Obsidian / Telegram 目录；嵌入笔记仅按选中文章的引用展开。

具体边界与移除方法见 [连接与数据说明](docs/SECURITY.md)。

## 从源码构建

需要 Xcode Command Line Tools 和 Swift 6.0+：

```sh
git clone https://github.com/chasepal/kindle-push-macos.git
cd kindle-push-macos
brew install python pandoc
./script/build_and_run.sh --verify
```

产物为 `mac-app/dist/Kindle 推送.app`。只编译不启动：`./script/build_and_run.sh --build-only`。

```sh
python3 -m unittest discover -s wifi-push -p 'test_*.py' -v
./script/package_release.sh
```

代码结构、打包过程见 [开发文档](docs/DEVELOPMENT.md)。

## 致谢与许可

- [乔木 SimpleUI](https://github.com/joeseesun/qiaomu-simpleui)：项目灵感与 Kindle 阅读体验。
- [KOReader](https://github.com/koreader/koreader) / [SSH 插件文档](https://github.com/koreader/koreader/wiki/SSH)：Kindle 端阅读和 SSH 能力。
- [Pandoc](https://pandoc.org/)：Markdown / EPUB 转换。

本项目自有代码使用 [MIT](LICENSE) 许可。KOReader、SimpleUI、Pandoc 按各自许可证分发，本仓库不打包这些项目的程序或代码。应用图标由 AI 生成，源图与提示词位于 `mac-app/Assets/`。
