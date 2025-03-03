import tkinter as tk
from tkinter import filedialog, messagebox
import re
import pyperclip
import uuid

# ---------------------- GLOBALS ----------------------
loaded_buses = {}         # {bus_name: [member1, member2, ...]}
bus_vars = {}             # {bus_name: BooleanVar} para el checkbox de cada bus
bus_list_order = []       # Para mantener el orden en que se insertan los buses
bus_member_vars = {}      # {bus_name: {member: BooleanVar}} para selección manual de miembros

current_bus_frame = None  # Referencia al frame actual en el panel derecho (solo uno a la vez)

# ---------------------- FILE LOADING ----------------------
def open_file_dialog():
    file_path = filedialog.askopenfilename(
        filetypes=[("KiCad Schematic", "*.kicad_sch")],
        title="Select a KiCad file"
    )
    return file_path

def load_schematic():
    """
    Carga un archivo .kicad_sch y extrae los buses (bus_alias) junto con sus miembros.
    Luego, en el panel izquierdo, crea para cada bus un Checkbutton y un Botón.
    """
    file_path = open_file_dialog()
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.readlines()

        # Limpiar estructuras globales
        global loaded_buses, bus_vars, bus_list_order, bus_member_vars, current_bus_frame
        loaded_buses.clear()
        bus_vars.clear()
        bus_list_order.clear()
        bus_member_vars.clear()
        current_bus_frame = None

        # Limpiar el panel izquierdo
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

        # Crear en el panel izquierdo un frame por cada bus con un Checkbutton y un Botón
        for bus_name, members in loaded_buses.items():
            bus_list_order.append(bus_name)
            # Checkbox para marcar si se generará este bus
            var = tk.BooleanVar(value=False)
            bus_vars[bus_name] = var

            row_frame = tk.Frame(frame_buses_left)
            row_frame.pack(fill=tk.X, padx=5, pady=2)

            chk = tk.Checkbutton(row_frame, variable=var)
            chk.pack(side=tk.LEFT)

            btn = tk.Button(row_frame, text=bus_name, anchor="w",
                            command=lambda b=bus_name: show_bus_members(b))
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        messagebox.showinfo("Load Successful", f"Found {len(loaded_buses)} buses.")

    except Exception as e:
        messagebox.showerror("Error Reading File", str(e))

# ---------------------- MANUAL MODE (SHOW MEMBERS) ----------------------
def show_bus_members(bus_name):
    """
    Muestra en el panel derecho los miembros del bus `bus_name`,
    sustituyendo cualquier vista previa de otro bus.
    Se conservan las selecciones previas gracias a bus_member_vars.
    """
    if not manual_mode_var.get():
        return  # Si no estamos en modo manual, no se muestra nada

    global current_bus_frame
    # Destruir la vista previa anterior si existía
    if current_bus_frame is not None:
        current_bus_frame.destroy()
        current_bus_frame = None

    # Crear un frame nuevo para mostrar este bus
    current_bus_frame = tk.Frame(frame_members_right, relief=tk.RIDGE, borderwidth=1)
    current_bus_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Título
    lbl_title = tk.Label(current_bus_frame, text=f"Bus: {bus_name}", font=("Arial", 10, "bold"))
    lbl_title.pack(anchor="w", padx=5, pady=5)

    # Asegurarnos de tener un diccionario de booleanvars para este bus
    if bus_name not in bus_member_vars:
        bus_member_vars[bus_name] = {}
        # Inicializar las vars con True (o False) por defecto
        for member in loaded_buses[bus_name]:
            bus_member_vars[bus_name][member] = tk.BooleanVar(value=True)

    # Crear checkbuttons para cada miembro
    for member in loaded_buses[bus_name]:
        var = bus_member_vars[bus_name][member]
        chk = tk.Checkbutton(current_bus_frame, text=member, variable=var, anchor="w")
        chk.pack(fill=tk.X, padx=10, pady=1)

# ---------------------- TOGGLE MANUAL MODE ----------------------
def toggle_manual_mode():
    """
    Si el modo manual está activo, se muestra el panel derecho;
    de lo contrario, se oculta y se borra cualquier vista previa.
    """
    if manual_mode_var.get():
        frame_members_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    else:
        # Ocultar el panel derecho
        for widget in frame_members_right.winfo_children():
            widget.destroy()
        global current_bus_frame
        current_bus_frame = None
        frame_members_right.forget()

# ---------------------- GENERATE CODE ----------------------
def generate_code():
    """
    Genera el código KiCad para los buses marcados en sus checkboxes (panel izquierdo).
    - Si manual mode está activo, se usan solo los miembros cuyos checkbuttons estén marcados.
    - Si manual mode está desactivado, se usan todos los miembros del bus.
    Cada bus se desplaza horizontalmente con un offset de (connection_length + 10).
    """
    # Recolectar buses que tienen su checkbox marcado
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

        # Determinar las señales de este bus
        if manual_mode_var.get():
            # Si no se ha cargado aún la vista de este bus, no tenemos su bus_member_vars
            if bus_name not in bus_member_vars:
                messagebox.showwarning("No Members Loaded",
                                       f"You haven't viewed bus '{bus_name}' in manual mode. "
                                       "Please click its button to load its members.")
                return
            # Tomar solo los miembros marcados
            signals = [
                m for (m, var) in bus_member_vars[bus_name].items() if var.get()
            ]
            if not signals:
                messagebox.showwarning("No Members Selected",
                                       f"Bus '{bus_name}' has no members selected.")
                return
        else:
            # Modo no manual: usar todos los miembros
            signals = loaded_buses[bus_name]

        # --- 1) Hierarchical label ---
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

        # --- 2) Initial horizontal bus ---
        bus_uuid = str(uuid.uuid4())
        code += f'(bus\n'
        code += f'\t(pts\n'
        code += f'\t\t(xy {current_start_x - 2.54} {start_y}) (xy {current_start_x} {start_y})\n'
        code += f'\t)\n'
        code += f'\t(stroke (width 0) (type default))\n'
        code += f'\t(uuid "{bus_uuid}")\n'
        code += f')\n'
        
        # --- 3) First vertical segment ---
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
        
        # --- 4) Bus entries for each signal ---
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

# ---------------------- UI SETUP ----------------------
root = tk.Tk()
root.title("KiCad Bus Generator")
root.geometry("900x600")

# 1) Checkbutton para modo manual
manual_mode_var = tk.BooleanVar(value=False)
chk_manual = tk.Checkbutton(root, text="Manual member selection", variable=manual_mode_var, command=toggle_manual_mode)
chk_manual.pack(pady=5)

# 2) Frame principal: izquierda (buses) y derecha (miembros en modo manual)
frame_main = tk.Frame(root)
frame_main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

# 2a) Panel Izquierdo
frame_buses_left = tk.Frame(frame_main)
frame_buses_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# 2b) Panel Derecho (para miembros), inicialmente oculto
frame_members_right = tk.Frame(frame_main, relief=tk.SUNKEN, borderwidth=1)

# 3) Frame para configuración
config_frame = tk.Frame(root)
config_frame.pack(pady=10)

tk.Label(config_frame, text="Spacing:").grid(row=0, column=0, padx=5)
entry_spacing = tk.Entry(config_frame, width=5)
entry_spacing.grid(row=0, column=1, padx=5)
entry_spacing.insert(0, "2.54")

tk.Label(config_frame, text="Connection Length:").grid(row=1, column=0, padx=5)
entry_length = tk.Entry(config_frame, width=5)
entry_length.grid(row=1, column=1, padx=5)
entry_length.insert(0, "10.16")

# 4) Botones de cargar y generar
btn_load = tk.Button(root, text="Load KiCad Schematic (.kicad_sch)", command=load_schematic)
btn_load.pack(pady=10)

btn_generate = tk.Button(root, text="Generate Code and Copy", command=generate_code)
btn_generate.pack(pady=10)

root.mainloop()
