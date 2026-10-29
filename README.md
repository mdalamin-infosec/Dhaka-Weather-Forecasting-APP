
<div align="center">

# 🌦️ Dhaka Weather Forecasting

**Explore • Analyze • Forecast**

A Python desktop application for exploring **Dhaka's historical weather (2019–2024)** through a Tkinter GUI.

[**Features**](#-features) · [**Workflow**](#-how-it-works) · [**Quick Start**](#-quick-start) · [**Structure**](#-project-structure)

</div>

---

## 📊 Project at a Glance

| 📍 Location | 📅 Period | ⏱️ Resolution | 📁 Dataset |
|:---:|:---:|:---:|:---:|
| **Dhaka** | **2019–2024** | **Hourly** | **52,608 records** |

Built around a bundled **NASA POWER–labeled historical dataset** to demonstrate beginner-friendly data processing, visual analysis, and forecasting.

## ✨ Features

| Feature | What it does |
|:---|:---|
| 🖥️ **Dashboard** | Displays weather summaries and trends |
| 📝 **Records** | Search, add, edit, delete, and save weather records |
| 📈 **Analysis** | Explore monthly/yearly trends and statistics |
| 🔮 **Forecast** | Generate up to **24 hourly estimates** using moving averages |
| 🎯 **Evaluation** | Calculate **MAE** and **RMSE** for forecast errors |
| ⚠️ **Event Screening** | Identify observations exceeding selected thresholds |
| 📤 **Export** | Save results to **CSV, JSON, and TXT** |

## 🔄 How It Works

**Application workflow** (static graphic — no Mermaid loading):

```text
         ┌────────────────────────┐
         │  Historical Weather CSV│
         └────────────┬───────────┘
                      ▼
         ┌────────────────────────┐
         │  Load & Organize Data  │
         └────────────┬───────────┘
                      ▼
         ┌────────────────────────┐
         │    Tkinter Desktop GUI │
         └────────────┬───────────┘
                      ▼
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
   [Records]      [Analysis]     [Forecast]
       └──────────────┼──────────────┘
                      ▼
               CSV / JSON / TXT
```

**Forecasting pipeline**

| ① Historical observations | ② Moving average | ③ Hourly estimates | ④ Error metrics |
|:---:|:---:|:---:|:---:|
| Load past data | Calculate recent mean | Up to 24 hours | MAE & RMSE |

> **Academic scope:** Forecasts are historical educational estimates, **not** live weather predictions, machine-learning models, or official weather warnings.

## 🚀 Quick Start

### 🐧 Linux (Debian / Ubuntu)

```bash
sudo apt update
sudo apt install python3 python3-tk git -y

git clone https://github.com/mdalamin-infosec/Dhaka-Weather-Forecasting-APP.git
cd Dhaka-Weather-Forecasting-APP
python3 main.py
```

**Terminal mode:** `python3 main.py --cli`

### 🪟 Windows 10 / 11

Install [Python 3](https://www.python.org/downloads/windows/) (including **Tkinter**) and [Git](https://git-scm.com/downloads/win). Then open **PowerShell**:

```powershell
git clone https://github.com/mdalamin-infosec/Dhaka-Weather-Forecasting-APP.git
cd Dhaka-Weather-Forecasting-APP
py main.py
```

**Terminal mode:** `py main.py --cli`  
**Alternative:** If `py` is unavailable, use `python` instead.

> **Before running:** The repository must contain `main.py`, the `src/` modules, and the dataset in `data/`. Empty placeholder folders alone cannot run the application. No third-party Python packages are required by the supplied project.

## 🗂️ Project Structure

```text
Dhaka-Weather-Forecasting-APP/
├── main.py               # GUI / CLI entry point
├── requirements.txt      # Dependency notes
├── README.md
├── src/                  # Application logic and Tkinter GUI
├── data/                 # Historical and editable CSV data
├── output/               # Exported analysis and forecasts
├── docs/                 # Documentation
├── figures/              # Figures (currently optional)
├── screenshots/          # GUI screenshots (currently optional)
└── reports/              # Reports (currently optional)
```

## 🧠 Python Concepts Demonstrated

`Classes & Objects` · `Functions` · `If/Else` · `Loops` · `Lists & Dictionaries` · `CSV/JSON` · `File Handling` · `Tkinter`

---

<div align="center">

**CSC 4162 — Programming in Python | Mid-Term Project | Fall 2026–2027**

Data source: [NASA POWER](https://power.larc.nasa.gov/) · GitHub: [@mdalamin-infosec](https://github.com/mdalamin-infosec)

</div>
