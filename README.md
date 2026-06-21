# Poker EV Trainer

一个适合新手的德州扑克 **EV（期望值）训练器**。  
输入你的手牌、公共牌、底池和跟注金额，程序会用 **Monte Carlo 模拟** 计算胜率，并给出 **Call / Fold** 建议。

---

## 功能

- 输入 2 张手牌（例如 `Ah Ks`）
- 输入 0–5 张公共牌（例如 `2h 7d Tc`，翻前可留空）
- 输入底池大小和跟注金额
- Monte Carlo 模拟计算 **Win % / Tie % / Lose %**
- 输出 **Pot Odds、Required Equity、Call EV** 及建议

---

## 环境要求

- **Windows 10 / 11**
- **Python 3.9 或更高版本**（推荐 3.10+）

---

## 第一步：检查 Python 是否已安装

打开 **PowerShell** 或 **命令提示符（CMD）**，输入：

```powershell
python --version
```

如果看到类似 `Python 3.11.x` 的输出，说明已安装，可跳到 **第二步**。

如果提示找不到命令，请先到官网安装 Python：  
https://www.python.org/downloads/

> 安装时务必勾选 **"Add Python to PATH"**（添加到环境变量）。

---

## 第二步：进入项目文件夹

在终端中输入（请把路径改成你实际存放项目的位置）：

```powershell
cd "D:\poker project"
```

确认当前目录下有这些文件：

```powershell
dir
```

应能看到：`app.py`、`requirements.txt`、`README.md`

---

## 第三步：创建虚拟环境（推荐）

虚拟环境可以隔离项目依赖，避免和其他 Python 项目冲突。

```powershell
python -m venv venv
```

激活虚拟环境：

```powershell
.\venv\Scripts\activate
```

激活成功后，命令行前面会出现 `(venv)` 字样。

---

## 第四步：安装依赖

确保仍在项目目录，且虚拟环境已激活（有 `(venv)` 前缀），然后输入：

```powershell
pip install -r requirements.txt
```

等待安装完成，应看到 `streamlit` 和 `treys` 安装成功。

---

## 第五步：运行程序

```powershell
streamlit run app.py
```

终端会显示类似：

```
Local URL: http://localhost:8501
```

浏览器通常会自动打开；如果没有，请手动访问：**http://localhost:8501**

---

## 第六步：停止程序

在运行程序的终端窗口按 **Ctrl + C** 即可停止。

下次使用时，只需重复：

```powershell
cd "D:\poker project"
.\venv\Scripts\activate
streamlit run app.py
```

---

## 使用示例

| 输入项 | 示例值 |
|--------|--------|
| 手牌 | `Ah Ks` |
| 公共牌 | `2h 7d Tc` |
| 底池 | `100` |
| 跟注 | `50` |

点击 **「计算胜率与 EV」** 后，页面会显示胜率、Pot Odds、Call EV 以及 Call / Fold 建议。

---

## 牌面格式说明

| 含义 | 写法 |
|------|------|
| 点数 | `2 3 4 5 6 7 8 9 T J Q K A`（T = 10） |
| 花色 | `h`=红桃 ♥　`d`=方块 ♦　`c`=梅花 ♣　`s`=黑桃 ♠ |
| 示例 | `Ah` = 红桃 A，`Ks` = 黑桃 K |

手牌和公共牌之间用空格分隔，例如：`Ah Ks` 和 `2h 7d Tc`

---

## 输出指标说明

| 指标 | 含义 |
|------|------|
| **Win %** | 模拟中赢牌的概率 |
| **Tie %** | 模拟中平局的概率 |
| **Lose %** | 模拟中输牌的概率 |
| **Pot Odds** | 底池赔率 = 跟注 / (底池 + 跟注) |
| **Required Equity** | 跟注所需最低胜率（盈亏平衡点） |
| **Call EV** | 跟注的期望值；≥ 0 建议 Call，< 0 建议 Fold |

---

## 常见问题

**Q：提示 `python` 不是内部或外部命令？**  
A：Python 未加入 PATH，请重新安装并勾选 "Add Python to PATH"。

**Q：提示 `streamlit` 不是内部或外部命令？**  
A：先激活虚拟环境 `.\venv\Scripts\activate`，再运行 `pip install -r requirements.txt`。

**Q：模拟很慢？**  
A：在页面上把「模拟次数」调低（例如 5000），速度会更快，精度略降。

**Q：翻前（没有公共牌）能算吗？**  
A：可以。公共牌留空即可，程序会在模拟中随机发完 5 张公共牌。

---

## 项目文件

```
poker project/
├── app.py              # 主程序（Streamlit 界面 + Monte Carlo 逻辑）
├── requirements.txt    # Python 依赖
├── README.md           # 本说明文档
└── venv/               # 虚拟环境（运行第三步后自动生成）
```

---

## 技术栈

- **Python** — 编程语言
- **Streamlit** — 网页界面
- **treys** — 德州扑克牌力计算
