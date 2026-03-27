# 🕊️ PigeonLab Setup Guide

> **Everything you need to get PigeonLab running on your Windows 11 computer — step by step, no technical experience required.**
>
> ⏱ **Total time: about 30–45 minutes**

---

## 📋 Table of Contents

| # | Section |
|---|---------|
| 1 | [What You Need](#1-what-you-need) |
| 2 | [Install Python 3.12](#2-install-python-312) |
| 3 | [Install Node.js](#3-install-nodejs) |
| 4 | [Install Git](#4-install-git) |
| 5 | [Install GPU Drivers & CUDA](#5-install-gpu-drivers--cuda) |
| 6 | [Install PyTorch](#6-install-pytorch) |
| 7 | [Set Up PigeonLab](#7-set-up-pigeonlab) |
| 8 | [Set Up SAM 3 (The AI Model)](#8-set-up-sam-3-the-ai-model) |
| 9 | [Launch PigeonLab](#9-launch-pigeonlab-) |
| 10 | [How To Use PigeonLab](#10-how-to-use-pigeonlab) |
| 11 | [Troubleshooting](#11-troubleshooting) |
| 12 | [Daily Startup](#12-daily-startup) |

---

> 💡 **Before you begin:** You will download and install several free programs. Each one is safe, from official sources, and used by researchers and developers worldwide. None of them cost anything.

---

## 1. What You Need

Make sure your computer meets these requirements before you start. If anything is missing, don't worry — we'll install everything together.

| Requirement | Details |
|-------------|---------|
| 🖥️ **Windows 11 (64-bit)** | Press `Windows + Pause` and look for "64-bit operating system" |
| 🎮 **NVIDIA GPU** | Any modern NVIDIA graphics card (RTX series, A6000, etc.) |
| 💾 **20 GB Free Disk Space** | For software, AI models, and your video files |
| 🌐 **Internet Connection** | Needed for setup only — PigeonLab works offline after |
| 🐍 **Python 3.12** | We'll install this in Step 2 |
| 📦 **Node.js 18+** | We'll install this in Step 3 |

### 🖥️ How to Open Command Prompt

Throughout this guide you'll need to type commands into **Command Prompt** — a black window where you type instructions.

**To open it:** Press the **Windows key**, type `cmd`, then press **Enter**.

Keep it open while working through the steps. To paste a command into Command Prompt, **right-click** inside the window.

---

## 2. Install Python 3.12

Python is the engine that runs PigeonLab's brain. Install it exactly as described — the version number matters.

### Step 2.1 — Download Python 3.12

👉 **[Download Python 3.12.10 (64-bit)](https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe)**

A file called `python-3.12.10-amd64.exe` will download to your Downloads folder.

### Step 2.2 — Run the Installer

> ⚠️ **CRITICAL — do not skip this!**
> On the very first screen of the installer, there is a checkbox at the bottom that says **"Add Python to PATH"**. You **MUST** check this box before clicking Install. If you miss it, Python won't work.

1. Double-click the downloaded file
2. ✅ Check **"Add Python 3.12 to PATH"**
3. Click **"Install Now"**
4. Wait for it to finish, then click **Close**

### Step 2.3 — Verify the Installation

Open a **new** Command Prompt window (close and reopen it), then run:

```
python --version
```

✅ **You should see:** `Python 3.12.10`

---

## 3. Install Node.js

Node.js powers the visual interface — the buttons, screens, and charts you'll see when using PigeonLab.

### Step 3.1 — Download and Install Node.js LTS

👉 **[Download Node.js LTS (Windows 64-bit)](https://nodejs.org/en/download)**

1. Click the big green **"LTS"** button
2. Run the downloaded `.msi` installer
3. Click **Next** through all the screens — the defaults are fine
4. Click **Finish** when done

### Step 3.2 — Verify the Installation

Open a new Command Prompt and run:

```
node --version
```

✅ **You should see something like:** `v22.x.x` — any number 18 or higher is fine.

---

## 4. Install Git

Git is a tool that lets you download PigeonLab onto your computer. Think of it as a very smart file copier.

### Step 4.1 — Download and Install Git for Windows

👉 **[Download Git for Windows](https://git-scm.com/download/win)**

1. Click the link — the download starts automatically
2. Run the installer and click **Next** through every screen
3. Click **Finish** when done

> ℹ️ There are many screens during the Git install. You do not need to change anything — just keep clicking **Next** and then **Finish**.

---

## 5. Install GPU Drivers & CUDA

CUDA is NVIDIA's toolkit that lets PigeonLab use your graphics card to process video at high speed. Without this, processing would be extremely slow.

### Step 5.1 — Update Your NVIDIA Drivers

👉 **[NVIDIA Driver Downloads](https://www.nvidia.com/en-us/drivers/)**

1. Select your GPU model and Windows 11 64-bit
2. Download and run the installer
3. Use **Express Installation**
4. Restart your computer when prompted

### Step 5.2 — Install CUDA Toolkit 12.6

👉 **[CUDA Toolkit 12.6 Download](https://developer.nvidia.com/cuda-12-6-0-download-archive)**

1. On the download page, select: **Windows → x86\_64 → 11 → exe (local)**
2. Download the installer (about 3 GB)
3. Run it and choose **Express Installation**
4. Restart your computer when it finishes

> ⚠️ **Restart required!** After CUDA installs, you must restart your computer before continuing.

### Step 5.3 — Verify CUDA is Working

```
nvidia-smi
```

✅ **You should see** a table showing your GPU name and CUDA version. If you see this, you're ready to continue.

---

## 6. Install PyTorch

PyTorch is the AI framework that PigeonLab uses to run the pigeon detection model.

### Step 6.1 — Install PyTorch with CUDA 12.6 Support

> 📋 Click to copy the command below, then paste it into Command Prompt (right-click to paste) and press **Enter**. Do not type it manually.

```
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

This downloads about 2–3 GB. You'll see a lot of text scrolling — that's normal. Wait until the `C:\>` cursor returns.

✅ **When it finishes** you'll see "Successfully installed torch..." in the output.

### Step 6.2 — Verify PyTorch Can See Your GPU

```
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

✅ **You should see:**
```
True
NVIDIA RTX A6000
```
The first line must say `True`. The second line shows your GPU name.

---

## 7. Set Up PigeonLab

Now we download PigeonLab itself and install all its remaining dependencies. Run these commands one at a time, in order.

> 📂 **Where to put PigeonLab:** We recommend your Documents folder. The commands below use that location.

### Step 7.1 — Download PigeonLab

```
cd %USERPROFILE%\Documents
git clone https://github.com/YOUR-ORG/pigeonlab.git
cd pigeonlab
```

> ⚠️ **Replace the URL** with the actual PigeonLab repository address your lab administrator provides. It will look like `https://github.com/labname/pigeonlab.git`

### Step 7.2 — Install All Python Packages

```
cd backend
pip install -r requirements.txt
```

This installs FastAPI, SQLite tools, image processing libraries, HuggingFace Hub, and everything else PigeonLab needs. It may take 3–5 minutes.

### Step 7.3 — Install the Frontend Interface

```
cd ..\frontend
npm install
```

You'll see a lot of text scroll by — this is normal. Wait for the cursor to return.

### Step 7.4 — Run the Environment Check

```
cd ..\backend
python scripts\setup_check.py
```

This runs **16 checks** on your system. Each item should show a ✅ green checkmark.

> ℹ️ The only items that may show ❌ at this point are the SAM 3 checks — that's expected and fine. We'll fix those in the next step. If any other item shows ❌, see the [Troubleshooting](#11-troubleshooting) section.

---

## 8. Set Up SAM 3 (The AI Model)

SAM 3 is the AI model that finds and tracks pigeons in your videos. It's made by Meta (Facebook) and hosted on HuggingFace — a platform for sharing AI models.

> ⏳ **This step involves a waiting period.** After requesting access on HuggingFace, you may need to wait a few hours or up to a day for approval. You can continue to Step 9 and load some sample data while you wait — PigeonLab works without the AI model for exploring the interface.

### Step 8.1 — Create a Free HuggingFace Account

👉 **[Create a free HuggingFace account](https://huggingface.co/join)**

1. Fill in your name, email, and a password
2. Verify your email address (check your inbox)

### Step 8.2 — Request Access to SAM 3

👉 **[SAM 3 Model Page](https://huggingface.co/facebook/sam3)**

1. Make sure you're logged in to HuggingFace
2. Visit the link above
3. Click the **"Request access"** button on the page
4. Fill in any requested information and submit
5. You'll receive an email when access is granted (usually within a day)

### Step 8.3 — Log In to HuggingFace on Your Computer

Run these two commands after your access is approved:

```
pip install huggingface_hub
huggingface-cli login
```

The second command will ask for a token. To get your token:

1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Click **"New token"**, give it a name, and click **Generate**
3. Copy the token (it starts with `hf_`)
4. Paste it into Command Prompt when asked, then press Enter

### Step 8.4 — Download the SAM 3 Model Files

> ☕ This downloads about 3–4 GB. Leave it running and go get a coffee — it may take 10–30 minutes depending on your internet speed. **Do not close the Command Prompt window while it's running.**

```
cd %USERPROFILE%\Documents\pigeonlab\backend
python scripts\download_sam3.py
```

✅ **When it finishes** you'll see:
```
SAM 3 downloaded to data/models/sam3. You can now start PigeonLab.
```

### Step 8.5 — Run the Setup Check One More Time

```
python scripts\setup_check.py
```

✅ **All 16 checks should now show ✅** — if they do, PigeonLab is fully set up and ready to use!

---

## 9. Launch PigeonLab 🎉

You're ready! There are two ways to start PigeonLab.

### ⭐ Easy Way — Double-Click to Start (Recommended)

1. Open File Explorer and navigate to your `pigeonlab` folder
2. Double-click the file called **`start.bat`**
3. Two black windows will open — leave them both running
4. Wait about 10 seconds, then open your browser
5. Go to: **`http://localhost:5173`**

🎉 **PigeonLab is running!** Bookmark this address for quick access every day.

### Alternative — Manual Start (Two Command Prompt Windows)

Use this if `start.bat` doesn't work.

**Window 1 — Backend (open a Command Prompt and run):**

```
cd %USERPROFILE%\Documents\pigeonlab\backend
uvicorn main:app --reload --port 8000
```

**Window 2 — Frontend (open a second Command Prompt and run):**

```
cd %USERPROFILE%\Documents\pigeonlab\frontend
npm run dev
```

Then open your browser and go to **`http://localhost:5173`**

### Optional — Load Sample Data

To see what PigeonLab looks like with data already in it, run this while PigeonLab is running:

```
cd %USERPROFILE%\Documents\pigeonlab\backend
python seed_data.py
```

This loads 4 sample pigeons (Alpha, Beta, Gamma, Delta), sample videos, and example analysis results so you can explore all the features right away.

---

## 10. How To Use PigeonLab

Here's how to do the most common tasks. Everything is designed to be straightforward, but these guides will get you started quickly.

---

### 📹 Process Your First Video

PigeonLab will find, track, and analyze all the pigeons automatically.

1. Click **Videos** in the left sidebar
2. Click the **+ Add Videos** button
3. Enter the path to your video file (e.g. `C:\Videos\session01.mp4`)
4. Select the camera type (Overhead, Side, Corner, etc.)
5. Enter how many pigeons are in the video
6. Click **Process Videos** — a progress bar will appear while it works

---

### 🐦 Confirm Pigeon Identities

Tell PigeonLab which pigeon is which so it can track them across sessions.

1. On the Home screen, look for the **"Needs Your Attention"** section
2. Click **Review Now** next to "unconfirmed pigeon identities"
3. You'll see a pigeon highlighted in the video frame
4. Click the matching pigeon card (Alpha, Beta, Gamma, Delta)
5. Repeat for each pigeon — use **Skip for Now** if you're unsure

---

### ⚡ Review Quality Flags

When the system spots something unusual in a video, it flags it for your review.

1. On the Home screen, click **Check Frames** under "Needs Your Attention"
2. You'll see the flagged frame with a plain-language description of the issue
3. Click **Looks Fine** if it looks correct to you
4. Click **Fix This** to go to the video and correct it manually

---

### 🗺️ View Heatmaps & Insights

See where your pigeons spend their time and how they interact with each other.

1. Click **Insights** in the left sidebar
2. Use the **time period** selector (Day / Week / Month / All) to choose a range
3. Click a pigeon's name to filter the heatmap to just that pigeon
4. Scroll down to see the **Social Map** (who spends time near whom)
5. Click **Export Data as CSV** to download your data as a spreadsheet

---

### 🐦 Register a New Pigeon

Add a new pigeon before processing videos that include it.

1. Click **Pigeons** in the left sidebar
2. Click **+ Register New** in the top right corner
3. Enter the pigeon's name and physical description (leg band color, markings, etc.)
4. Click **Save** — the pigeon is now in the system

---

### 📊 Export Your Data

Download your research data as spreadsheet-ready CSV files.

1. Click **Insights** in the left sidebar
2. Scroll to the bottom of the page
3. Click **Export Data as CSV**
4. Choose what to include: positions, behaviors, social proximity data
5. Click **Export** — files download to your computer automatically

---

### 📽️ Watch a Video With Overlays

Watch any processed video with colored outlines drawn around each pigeon.

1. Click **Videos** in the left sidebar
2. Find your video and click **Watch ▶**
3. Use the slider at the bottom to scrub through the video
4. Press the **← →** arrow keys on your keyboard to step frame by frame
5. The pigeon cards below the video show who is in the frame and where

---

### 🏋️ Train a Behavior Model

Teach PigeonLab to automatically recognize specific behaviors like feeding, resting, or preening.

1. Click **Training** in the left sidebar
2. Go to the **Label Clips** tab and label at least 20 video clips per behavior type
3. Once you have enough labels, click the **Train Model** tab
4. Configure the settings (you can leave the defaults as they are)
5. Click **Launch Training** and wait for it to complete
6. When done, click **Set as Active** to use the new model on future videos

---

## 11. Troubleshooting

Something not working? Find your problem below and follow the fix.

| ❌ What you see | ✅ What it means & how to fix it |
|----------------|----------------------------------|
| `python is not recognized` | Python wasn't added to PATH during installation. Uninstall Python, reinstall it, and make sure to check **"Add Python to PATH"** on the first screen. |
| `npm is not recognized` | Node.js didn't install correctly. Close Command Prompt, reopen it, and try again. If still broken, reinstall Node.js. |
| `torch.cuda.is_available()` returns `False` | PyTorch can't find your GPU. Make sure CUDA 12.6 is installed and your NVIDIA drivers are up to date. Then reinstall PyTorch using the command in Step 6. |
| Browser shows "This site can't be reached" | PigeonLab isn't running. Make sure both Command Prompt windows are open and running. Look for the message "Application startup complete" in the backend window. |
| "Access denied" when downloading SAM 3 | Your HuggingFace access hasn't been approved yet, or you aren't logged in. Run `huggingface-cli login` again and check your email for an approval message. |
| Video stays stuck at "Queued" forever | SAM 3 model files may not have downloaded. Run `python scripts\setup_check.py` to check. If the checkpoint shows ❌, re-run `python scripts\download_sam3.py`. |
| The page is blank or shows an error | Press **F12** in your browser, click **Console**, and look for red error messages. The most common cause is the backend not running — check the first Command Prompt window. |
| `ModuleNotFoundError` for any package | A package didn't install properly. Run `pip install -r requirements.txt` again from the `pigeonlab\backend` folder. |
| Heatmaps or charts are blank | No data has been processed yet. Run `python seed_data.py` from the backend folder to load example data and see the interface in action. |
| `nvidia-smi is not recognized` | Your NVIDIA drivers aren't installed or need updating. Download the latest driver from [nvidia.com/drivers](https://www.nvidia.com/en-us/drivers/) and restart your computer. |

---

## 12. Daily Startup

Once PigeonLab is set up, starting it each day is quick and simple.

### ⭐ The Fastest Way

1. Double-click **`start.bat`** in your `pigeonlab` folder
2. Wait 10 seconds
3. Open your browser and go to **`http://localhost:5173`**

That's it.

> 🔖 **Pro tip:** Bookmark `http://localhost:5173` in your browser as "PigeonLab". Every morning: double-click `start.bat`, click your bookmark.

> 🛑 **To stop PigeonLab:** Close both black Command Prompt windows. Your data is automatically saved — you won't lose anything.

---

### Quick Reference — URLs When PigeonLab Is Running

| URL | What it is |
|-----|-----------|
| `http://localhost:5173` | 🏠 PigeonLab main interface — this is what you use every day |
| `http://localhost:8000/docs` | 📖 API documentation (for advanced users) |
| `http://localhost:8000/api/health` | 💚 Backend health check — confirms the server is running |

---

## Summary of All Install Commands

If you need to reference all the commands in one place, here they are in order:

```bash
# Step 6 — PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126

# Step 7 — PigeonLab setup
cd %USERPROFILE%\Documents
git clone https://github.com/YOUR-ORG/pigeonlab.git
cd pigeonlab\backend
pip install -r requirements.txt
cd ..\frontend
npm install
cd ..\backend
python scripts\setup_check.py

# Step 8 — SAM 3
pip install huggingface_hub
huggingface-cli login
python scripts\download_sam3.py
python scripts\setup_check.py

# Step 9 — Launch
cd %USERPROFILE%\Documents\pigeonlab
start.bat

# Optional — load sample data
cd %USERPROFILE%\Documents\pigeonlab\backend
python seed_data.py
```

---

*🕊️ PigeonLab — Pigeon behavioral research platform · Windows 11 · NVIDIA GPU*
*Built with FastAPI · React 19 · SAM 3 · TailwindCSS · SQLite*
