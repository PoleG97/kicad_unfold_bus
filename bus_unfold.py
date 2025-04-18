import os
import configparser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from ttkthemes import ThemedTk
import re
import pyperclip
import uuid

# ---------------------- CONFIGURACIÓN ----------------------
CONFIG_FILE = "config.ini"
config = configparser.ConfigParser()

# Si no existe el archivo config.ini, se crea con valores por defecto
if not os.path.exists(CONFIG_FILE):
    config["DEFAULT"] = {
        "theme": "yaru",
        "spacing": "2.54",
        "connection_length": "10.16"
    }
    with open(CONFIG_FILE, "w") as f:
        config.write(f)
else:
    config.read(CONFIG_FILE)

default_theme = config["DEFAULT"].get("theme", "yaru")
default_spacing = config["DEFAULT"].get("spacing", "2.54")
default_connection_length = config["DEFAULT"].get("connection_length", "10.16")

# ---------------------- GLOBALS ----------------------
loaded_buses = {}         # {bus_name: [member1, member2, ...]}
bus_vars = {}             # {bus_name: BooleanVar} for each bus's checkbox
bus_list_order = []       # To maintain the order in which buses are added
bus_member_vars = {}      # {bus_name: {member: BooleanVar}} for manual member selection

current_bus_frame = None  # Reference to the current frame in the right panel (only one at a time)

# ---------------------- FILE LOADING ----------------------
def open_file_dialog():
    file_path = filedialog.askopenfilename(
        filetypes=[("KiCad Schematic", "*.kicad_sch")],
        title="Select a KiCad file"
    )
    return file_path

def load_schematic():
    """
    Loads a .kicad_sch file and extracts the buses (bus_alias) along with their members.
    Then, in the left panel, creates a Checkbutton and a Button for each bus.
    """
    file_path = open_file_dialog()
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.readlines()

        # Clear global structures
        global loaded_buses, bus_vars, bus_list_order, bus_member_vars, current_bus_frame
        loaded_buses.clear()
        bus_vars.clear()
        bus_list_order.clear()
        bus_member_vars.clear()
        current_bus_frame = None

        # Clear the left panel
        for widget in frame_buses_left.winfo_children():
            widget.destroy()

        inside_alias = False
        inside_members = False
        current_alias = None
        current_members = []
        alias_paren_count = 0
        members_paren_count = 0

        for line in content:
            line = line.strip()
            if line.startswith("(bus_alias"):
                inside_alias = True
                alias_paren_count = line.count("(") - line.count(")")
                parts = line.split('"')
                if len(parts) > 1:
                    current_alias = parts[1]
                current_members = []
                inside_members = False
                continue

            if inside_alias:
                alias_paren_count += line.count("(") - line.count(")")
                if not inside_members and "(members" in line:
                    inside_members = True
                    members_paren_count = line.count("(") - line.count(")")
                    members = re.findall(r'"(.*?)"', line)
                    current_members.extend(members)
                elif inside_members:
                    members = re.findall(r'"(.*?)"', line)
                    current_members.extend(members)
                    members_paren_count += line.count("(") - line.count(")")
                    if members_paren_count <= 0:
                        inside_members = False

                if alias_paren_count <= 0:
                    if current_alias:
                        loaded_buses[current_alias] = current_members
                    inside_alias = False
                    current_alias = None
                    current_members = []
                    inside_members = False

        if not loaded_buses:
            messagebox.showwarning("No Buses Found", "No Bus Aliases were found in the file.")
            return

        # Create in the left panel a frame for each bus with a Checkbutton and a Button
        for bus_name, members in loaded_buses.items():
            bus_list_order.append(bus_name)
            # Checkbox to mark if this bus will be generated
            var = tk.BooleanVar(value=False)
            bus_vars[bus_name] = var

            row_frame = ttk.Frame(frame_buses_left)
            row_frame.pack(fill=tk.X, padx=5, pady=2)

            chk = ttk.Checkbutton(row_frame, variable=var)
            chk.pack(side=tk.LEFT)

            btn = ttk.Button(row_frame, text=bus_name, command=lambda b=bus_name: show_bus_members(b))
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        messagebox.showinfo("Load Successful", f"Found {len(loaded_buses)} buses.")

    except Exception as e:
        messagebox.showerror("Error Reading File", str(e))

# ---------------------- MANUAL MODE (SHOW MEMBERS) ----------------------
def show_bus_members(bus_name):
    """
    Displays in the right panel the members of the bus `bus_name`,
    replacing any preview of another bus.
    Previous selections are preserved via bus_member_vars.
    """
    if not manual_mode_var.get():
        return  # If manual mode is not active, do not display anything

    global current_bus_frame
    if current_bus_frame is not None:
        current_bus_frame.destroy()
        current_bus_frame = None

    current_bus_frame = ttk.Frame(frame_members_right, relief="ridge")
    current_bus_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    lbl_title = ttk.Label(current_bus_frame, text=f"Bus: {bus_name}", font=("Arial", 10, "bold"))
    lbl_title.pack(anchor="w", padx=5, pady=5)

    if bus_name not in bus_member_vars:
        bus_member_vars[bus_name] = {}
        for member in loaded_buses[bus_name]:
            bus_member_vars[bus_name][member] = tk.BooleanVar(value=True)

    for member in loaded_buses[bus_name]:
        var = bus_member_vars[bus_name][member]
        chk = ttk.Checkbutton(current_bus_frame, text=member, variable=var)
        chk.pack(fill=tk.X, padx=10, pady=1)

# ---------------------- TOGGLE MANUAL MODE ----------------------
def toggle_manual_mode():
    """
    If manual mode is active, display the right panel;
    otherwise, hide it and clear any preview.
    """
    if manual_mode_var.get():
        frame_members_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    else:
        for widget in frame_members_right.winfo_children():
            widget.destroy()
        global current_bus_frame
        current_bus_frame = None
        frame_members_right.forget()

# ---------------------- GENERATE CODE ----------------------
def generate_code():
    """
    Generates the KiCad code for the buses marked in their checkboxes (left panel).
    - If manual mode is active, only the members whose checkbuttons are selected are used.
    - If manual mode is inactive, all members of the bus are used.
    Each bus is shifted horizontally with an offset of (connection_length + 10).
    """
    selected_buses = [b for b in bus_list_order if bus_vars[b].get()]
    if not selected_buses:
        messagebox.showwarning("Empty Selection", "Please check at least one bus to generate.")
        return

    try:
        default_start_x = 194.31
        start_y = 49.53
        spacing = float(entry_spacing.get())
        connection_length = float(entry_length.get())
    except ValueError:
        messagebox.showerror("Input Error", "Spacing and connection length values must be numbers.")
        return

    code = ""
    for idx, bus_name in enumerate(selected_buses):
        current_start_x = default_start_x + idx * (connection_length + 25)
        if manual_mode_var.get():
            if bus_name not in bus_member_vars:
                messagebox.showwarning("No Members Loaded",
                                       f"You haven't viewed bus '{bus_name}' in manual mode. "
                                       "Please click its button to load its members.")
                return
            signals = [m for (m, var) in bus_member_vars[bus_name].items() if var.get()]
            if not signals:
                messagebox.showwarning("No Members Selected",
                                       f"Bus '{bus_name}' has no members selected.")
                return
        else:
            signals = loaded_buses[bus_name]

        hlabel_uuid = str(uuid.uuid4())
        code += f'(hierarchical_label "{{{bus_name}}}"\n'
        code += f'\t(shape input)\n'
        code += f'\t(at {current_start_x - 2.54} {start_y} 180)\n'
        code += f'\t(effects\n'
        code += f'\t\t(font (size 1.27 1.27))\n'
        code += f'\t\t(justify right)\n'
        code += f'\t)\n'
        code += f'\t(uuid "{hlabel_uuid}")\n'
        code += f')\n'

        bus_uuid = str(uuid.uuid4())
        code += f'(bus\n'
        code += f'\t(pts\n'
        code += f'\t\t(xy {current_start_x - 2.54} {start_y}) (xy {current_start_x} {start_y})\n'
        code += f'\t)\n'
        code += f'\t(stroke (width 0) (type default))\n'
        code += f'\t(uuid "{bus_uuid}")\n'
        code += f')\n'
        
        if signals:
            end_y = start_y + spacing * len(signals)
            bus_uuid = str(uuid.uuid4())
            code += f'(bus\n'
            code += f'\t(pts\n'
            code += f'\t\t(xy {current_start_x} {start_y}) (xy {current_start_x} {end_y})\n'
            code += f'\t)\n'
            code += f'\t(stroke (width 0) (type default))\n'
            code += f'\t(uuid "{bus_uuid}")\n'
            code += f')\n'
        
        for i, signal in enumerate(signals):
            current_y = start_y + spacing * (i + 1)
            bus_entry_y = current_y - 2.54
            
            bus_entry_uuid = str(uuid.uuid4())
            code += f'(bus_entry\n'
            code += f'\t(at {current_start_x} {bus_entry_y})\n'
            code += f'\t(size 2.54 2.54)\n'
            code += f'\t(stroke (width 0) (type default))\n'
            code += f'\t(uuid "{bus_entry_uuid}")\n'
            code += f')\n'
            
            wire_start_x = current_start_x + 2.54
            wire_end_x = wire_start_x + connection_length
            
            wire_uuid = str(uuid.uuid4())
            code += f'(wire\n'
            code += f'\t(pts\n'
            code += f'\t\t(xy {wire_start_x} {current_y}) (xy {wire_end_x} {current_y})\n'
            code += f'\t)\n'
            code += f'\t(stroke (width 0) (type default))\n'
            code += f'\t(uuid "{wire_uuid}")\n'
            code += f')\n'
            
            label_uuid = str(uuid.uuid4())
            code += f'(label "{signal}"\n'
            code += f'\t(at {wire_end_x} {current_y} 180)\n'
            code += f'\t(effects\n'
            code += f'\t\t(font (size 1.27 1.27))\n'
            code += f'\t\t(justify right bottom)\n'
            code += f'\t)\n'
            code += f'\t(uuid "{label_uuid}")\n'
            code += f')\n'

    pyperclip.copy(code)
    messagebox.showinfo("Code Generated", "The bus code has been copied to the clipboard. Paste it into Eeschema.")

# ---------------------- THEME SELECTION ----------------------
def choose_theme():
    theme_window = tk.Toplevel(root)
    theme_window.title("Choose Theme")
    ttk.Label(theme_window, text="Select a theme:").pack(padx=10, pady=5)
    
    themes = root.get_themes()
    theme_combobox = ttk.Combobox(theme_window, values=themes, state="readonly")
    theme_combobox.pack(padx=10, pady=5)
    
    # Intenta establecer el tema actual como seleccionado
    current = root.tk.call("ttk::style", "theme", "use")
    if current in themes:
        theme_combobox.set(current)
    else:
        theme_combobox.current(0)
        
    def apply_theme():
        selected_theme = theme_combobox.get()
        root.set_theme(selected_theme)
        # Actualiza el archivo config.ini
        config["DEFAULT"]["theme"] = selected_theme
        with open(CONFIG_FILE, "w") as f:
            config.write(f)
        messagebox.showinfo("Theme Changed", f"Theme changed to {selected_theme}")
        theme_window.destroy()
    
    ttk.Button(theme_window, text="Apply", command=apply_theme).pack(padx=10, pady=10)

# ---------------------- UI SETUP ----------------------
root = ThemedTk(theme=default_theme)
style = ttk.Style(root)

root.title("KiCad Bus Generator")
root.geometry("900x600")

# Botón para elegir tema
theme_btn = ttk.Button(root, text="Choose Theme", command=choose_theme)
theme_btn.pack(pady=5)

# 1) Checkbutton for manual mode
manual_mode_var = tk.BooleanVar(value=False)
chk_manual = ttk.Checkbutton(root, text="Manual member selection", variable=manual_mode_var, command=toggle_manual_mode)
chk_manual.pack(pady=5)

# 2) Main frame: left (buses) and right (members in manual mode)
frame_main = ttk.Frame(root)
frame_main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

# 2a) Left panel
frame_buses_left = ttk.Frame(frame_main)
frame_buses_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# 2b) Right panel (for members), initially hidden
frame_members_right = ttk.Frame(frame_main)
# Se mostrará al activar el modo manual

# 3) Configuration frame
config_frame = ttk.Frame(root)
config_frame.pack(pady=10)

ttk.Label(config_frame, text="Spacing:").grid(row=0, column=0, padx=5)
entry_spacing = ttk.Entry(config_frame, width=5)
entry_spacing.grid(row=0, column=1, padx=5)
entry_spacing.insert(0, default_spacing)

ttk.Label(config_frame, text="Connection Length:").grid(row=1, column=0, padx=5)
entry_length = ttk.Entry(config_frame, width=5)
entry_length.grid(row=1, column=1, padx=5)
entry_length.insert(0, default_connection_length)

# 4) Buttons to load and generate
btn_load = ttk.Button(root, text="Load KiCad Schematic (.kicad_sch)", command=load_schematic)
btn_load.pack(pady=10)

btn_generate = ttk.Button(root, text="Generate Code and Copy", command=generate_code)
btn_generate.pack(pady=10)

root.mainloop()
