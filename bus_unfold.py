import tkinter as tk
from tkinter import filedialog, messagebox
import re
import pyperclip
import uuid

def open_file_dialog():
    file_path = filedialog.askopenfilename(
        filetypes=[("KiCad Schematic", "*.kicad_sch")],
        title="Select a KiCad file"
    )
    return file_path

def load_schematic():
    """
    Loads a .kicad_sch file and extracts Bus Aliases for code generation.
    """
    file_path = open_file_dialog()
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.readlines()

        bus_aliases = {}
        inside_alias = False
        inside_members = False
        current_alias = None
        current_members = []
        alias_paren_count = 0  # Parentheses counter for the alias block
        members_paren_count = 0  # Parentheses counter for the members block

        for line in content:
            line = line.strip()
            # Detect start of a bus alias
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
                # If not in the members block and the line contains "(members", start the block
                if not inside_members and "(members" in line:
                    inside_members = True
                    members_paren_count = line.count("(") - line.count(")")
                    # Extract members from the same line
                    members = re.findall(r'"(.*?)"', line)
                    current_members.extend(members)
                # If already in the members block, continue extracting
                elif inside_members:
                    members = re.findall(r'"(.*?)"', line)
                    current_members.extend(members)
                    members_paren_count += line.count("(") - line.count(")")
                    if members_paren_count <= 0:
                        inside_members = False
                # If the alias block is finished, save the alias
                if alias_paren_count <= 0:
                    if current_alias:
                        bus_aliases[current_alias] = current_members
                    inside_alias = False
                    current_alias = None
                    current_members = []
                    inside_members = False

        if not bus_aliases:
            messagebox.showwarning("No Buses Found", "No Bus Aliases were found in the file.")
            return

        listbox_buses.delete(0, tk.END)
        global loaded_buses
        loaded_buses = bus_aliases

        for alias in bus_aliases.keys():
            listbox_buses.insert(tk.END, alias)

        messagebox.showinfo("Load Successful", f"Found {len(loaded_buses)} buses.")

    except Exception as e:
        messagebox.showerror("Error Reading File", str(e))

def generate_code():
    """
    Generates KiCad code for the selected buses and copies it to the clipboard.
    When multiple buses are selected, each bus is generated next to the previous one,
    with a horizontal separation equal to (connection_length + 10).
    """
    selected = [listbox_buses.get(i) for i in listbox_buses.curselection()]
    if not selected:
        messagebox.showwarning("Empty Selection", "Please select at least one bus to generate.")
        return

    try:
        # Default starting coordinates
        default_start_x = 194.31
        start_y = 49.53
        spacing = float(entry_spacing.get())
        connection_length = float(entry_length.get())
    except ValueError:
        messagebox.showerror("Input Error", "Spacing and connection length values must be numbers.")
        return

    code = ""
    
    for idx, bus in enumerate(selected):
        # Calculate the current starting X position for this bus.
        current_start_x = default_start_x + idx * (connection_length + 30)
        signals = loaded_buses[bus]
        
        # --- 1) Hierarchical label for the bus with {} ---
        hlabel_uuid = str(uuid.uuid4())
        code += f'(hierarchical_label "{{{bus}}}"\n'
        code += f'\t(shape input)\n'
        code += f'\t(at {current_start_x - 2.54} {start_y} 180)\n'
        code += f'\t(effects\n'
        code += f'\t\t(font (size 1.27 1.27))\n'
        code += f'\t\t(justify right)\n'
        code += f'\t)\n'
        code += f'\t(uuid "{hlabel_uuid}")\n'
        code += f')\n'

        # --- 2) Initial horizontal bus (short) ---
        bus_uuid = str(uuid.uuid4())
        code += f'(bus\n'
        code += f'\t(pts\n'
        code += f'\t\t(xy {current_start_x - 2.54} {start_y}) (xy {current_start_x} {start_y})\n'
        code += f'\t)\n'
        code += f'\t(stroke (width 0) (type default))\n'
        code += f'\t(uuid "{bus_uuid}")\n'
        code += f')\n'
        
        # --- 3) First vertical segment of the main bus ---
        if len(signals) > 0:
            end_y = start_y + spacing * len(signals)
            bus_uuid = str(uuid.uuid4())
            code += f'(bus\n'
            code += f'\t(pts\n'
            code += f'\t\t(xy {current_start_x} {start_y}) (xy {current_start_x} {end_y})\n'
            code += f'\t)\n'
            code += f'\t(stroke (width 0) (type default))\n'
            code += f'\t(uuid "{bus_uuid}")\n'
            code += f')\n'
        
        # --- 4) Bus entries (bus_entry) for each signal and wires ---
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

# ---------------------- GRAPHICAL INTERFACE ----------------------
root = tk.Tk()
root.title("KiCad Bus Generator")
root.geometry("600x550")

loaded_buses = {}  # Dictionary to store loaded buses

btn_load = tk.Button(root, text="Load KiCad Schematic (.kicad_sch)", command=load_schematic)
btn_load.pack(pady=10)

listbox_buses = tk.Listbox(root, selectmode=tk.MULTIPLE, height=10, width=60)
listbox_buses.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

# Configuration frame now only includes Spacing and Connection Length
config_frame = tk.Frame(root)
config_frame.pack(pady=10)

tk.Label(config_frame, text="Spacing:").grid(row=0, column=0)
entry_spacing = tk.Entry(config_frame, width=5)
entry_spacing.grid(row=0, column=1)
entry_spacing.insert(0, "2.54")  # Default value

tk.Label(config_frame, text="Connection Length:").grid(row=1, column=0)
entry_length = tk.Entry(config_frame, width=5)
entry_length.grid(row=1, column=1)
entry_length.insert(0, "10.16")  # Default value

btn_generate = tk.Button(root, text="Generate Code and Copy", command=generate_code)
btn_generate.pack(pady=10)

root.mainloop()
