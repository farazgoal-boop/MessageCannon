import tkinter
import customtkinter
import sys
import os

sys.path.append(os.getcwd())

from src.ui.main_window import MainWindow

def run_test():
    try:
        app = MainWindow()
        app.withdraw()
        app.update_idletasks()
        
        # Switch to Settings view
        app._show_view("Settings")
        app.update_idletasks()
        
        # Find the frame named Settings among children
        settings_frame = None
        for child in app.winfo_children():
            if getattr(child, "_name", "") == "Settings" or "settings" in str(child).lower():
                # We need to find the actual frame object.
                # Usually it's in a main container.
                pass
        
        # Let's search recursively for a frame that might be the settings view
        def find_frame_by_name(container, name):
            if str(container).endswith(name.lower()):
                return container
            if hasattr(container, "winfo_children"):
                for child in container.winfo_children():
                    res = find_frame_by_name(child, name)
                    if res: return res
            return None

        # Just find the active view frame.
        # MainWindow likely sets self.current_view or similar.
        # Using a brute force discovery instead:
        all_frames = []
        def get_all_ctk_frames(container):
            if isinstance(container, customtkinter.CTkFrame):
                all_frames.append(container)
            if hasattr(container, "winfo_children"):
                for child in container.winfo_children():
                    get_all_ctk_frames(child)
        
        get_all_ctk_frames(app)
        # The Settings view is probably the one with most specific height or containing settings labels.
        # But wait, app.frames was a good guess based on common CTk patterns. 
        # Since it failed, let's look for how _show_view is implemented.
        
        # Actually, let's just find the frame that is visible and has labels like "Theme" or "License"
        target_frame = None
        for frame in all_frames:
            if frame.winfo_viewable():
                # Check if it has any label containing 'Settings' or 'Theme'
                for child in frame.winfo_children():
                    if isinstance(child, customtkinter.CTkLabel):
                        txt = str(child.cget("text")).lower()
                        if "theme" in txt or "settings" in txt or "license" in txt:
                            target_frame = frame
                            break
            if target_frame: break
            
        if not target_frame: 
            # Fallback: largest viewable frame
            viewable = [f for f in all_frames if f.winfo_viewable()]
            if viewable:
                target_frame = max(viewable, key=lambda f: f.winfo_height())

        settings_frame = target_frame
        
        if not settings_frame:
            print("Error: Could not find Settings frame")
            return

        def get_labels(container):
            labels = []
            if hasattr(container, "winfo_children"):
                for child in container.winfo_children():
                    if isinstance(child, customtkinter.CTkLabel):
                        labels.append(child)
                    labels.extend(get_labels(child))
            return labels

        def print_info(mode_name):
            print(f"--- Appearance Mode: {mode_name} ---")
            print(f"Appearance Mode (Actual): {customtkinter.get_appearance_mode()}")
            
            all_labels = get_labels(settings_frame)
            for i, label in enumerate(all_labels[:12]):
                try:
                    text = label.cget("text")
                    color = label.cget("text_color")
                    print(f"Label {i+1}: Text=\"{text}\", text_color={color}")
                except Exception as e:
                    print(f"Label {i+1}: Error getting info: {e}")
                    
            print(f"Settings View Frame Class: {settings_frame.__class__.__name__}")
            print(f"Settings View Frame Height: {settings_frame.winfo_height()}")
            print(f"Settings View Frame Requested Height: {settings_frame.winfo_reqheight()}")
            print(f"Root Window Height: {app.winfo_height()}")
            exceeds = settings_frame.winfo_reqheight() > app.winfo_height()
            print(f"Settings content exceeds window area: {exceeds}")

        # Initial mode
        print_info("Initial")
        
        # Switch to Light mode
        customtkinter.set_appearance_mode("Light")
        app.update_idletasks()
        print_info("Light")
        
        app.destroy()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
