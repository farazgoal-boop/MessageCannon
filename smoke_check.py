import customtkinter as ctk
import os
import sys

root_dir = os.path.abspath(".")
src_dir = os.path.join(root_dir, "src")
sys.path.insert(0, root_dir)
sys.path.insert(0, src_dir)

from src.ui.main_window import MainWindow

def get_widget_colors(widget):
    res = {}
    for attr in ["text_color", "fg_color", "text_color_disabled"]:
        try:
            val = widget.cget(attr)
            if val: res[attr] = val
        except: pass
    return res

app = MainWindow()
ctk.set_appearance_mode("Light")
app.update_idletasks()

print("--- Smoke Check Results (Light Theme) ---")

def find_all(root, res):
    res.append(root)
    for child in root.winfo_children():
        find_all(child, res)

all_w = []
find_all(app, all_w)

for w in all_w:
    try:
        txt = w.cget("text")
        if "Import" in txt:
            print(f"Match found '{txt}': {get_widget_colors(w)}")
        if "Settings" == txt:
            print(f"Settings Nav: {get_widget_colors(w)}")
    except: pass

app.withdraw()
app.destroy()
