# Create the GitHub repo and push (one-time)

Your project is ready to push. Follow these steps to create **PDF2XL AI Agent** on your GitHub account and push this code.

---

## 1. Create the repo on GitHub

1. Open: **https://github.com/new**
2. **Repository name:** `PDF2XL-AI-Agent` (GitHub uses hyphens; the display name can be "PDF2XL AI Agent" in the description).
3. **Description (optional):** e.g. `Extract tables from PDFs to Excel — with or without AI (Anthropic).`
4. Choose **Public** (or Private if you prefer).
5. **Do not** check "Add a README", "Add .gitignore", or "Choose a license" — we already have those in this project.
6. Click **Create repository**.

---

## 2. Connect this folder and push

After the repo is created, GitHub will show you commands. Use these (replace `YOUR_USERNAME` with your GitHub username):

```bash
cd /Users/m.w.zahoor/Desktop/pdf-excel

git remote add origin https://github.com/YOUR_USERNAME/PDF2XL-AI-Agent.git
git push -u origin main
```

If you use SSH instead of HTTPS:

```bash
git remote add origin git@github.com:YOUR_USERNAME/PDF2XL-AI-Agent.git
git push -u origin main
```

---

## 3. Optional: set repo display name

On the repo page: **Settings** → under "Repository name" you can add a **Description** like `PDF to Excel with optional AI extraction (Anthropic)`. The repo URL will stay `PDF2XL-AI-Agent`.

---

After this, all future work can be done on GitHub (clone, push, pull, issues, etc.).
