# KiCad Bus Generator

This project is a graphical tool designed to simplify the generation of bus code for KiCad schematics. The application extracts "bus_alias" definitions and their members from a `.kicad_sch` file, allowing users to manually select which members to include and then generate the necessary code for import into Eeschema.

---

## Objectives

- **Automate the process:** Automatically extract buses and their members from KiCad schematic files.
- **Custom selection:** Enable manual selection of bus members to have detailed control over which signals are included.
- **Code generation:** Create and copy the KiCad code required to integrate the buses into a schematic project.
- **Streamline design:** Reduce the time and effort needed to modify and update schematics in KiCad.

---

## Prerequisites

- **Python 3.x:** The application is developed in Python, so a recent version of Python 3 is required.
- **Tkinter:** Used for the graphical user interface; it is typically included with Python.
- **pyperclip:** Required to copy the generated code to the clipboard.  
  Install it using:
  ```bash
  pip install pyperclip
  ```
- **Standard modules:**  
  The application utilizes Python's built-in `re` and `uuid` modules.

---

## Installation

1. **Download or Clone the Repository:**  
   Download the source code or clone the repository to your local machine.

2. **Install Dependencies:**  
   Ensure that the required dependencies are installed (e.g., pyperclip). You can install them using pip:
   ```bash
   pip install pyperclip
   ```

3. **Run the Application:**  
   Navigate to the project directory and execute the script:
   ```bash
   python bus_unfold.py
   ```

---

## Usage

1. **Load the Schematic:**  
   Click the **"Load KiCad Schematic (.kicad_sch)"** button and select a `.kicad_sch` file from your system.

2. **View and Select Buses:**  
   - The left panel will display all the buses found in the file.
   - Check the box for each bus you wish to generate.
   - Optionally, enable **Manual Mode** to individually select bus members by clicking on the bus button.

   > [!NOTE]
   > In case to use the **Manual Mode**, you need to select the bus first and then click on the **Manual Mode** button. Then, keep clicking on the bus members to **unselect** them, by default all the members are selected to generate the code.

3. **Configuration:**  
   Adjust the **Spacing** and **Connection Length** values as needed for your design.

4. **Generate the Code:**  
   Click the **"Generate Code and Copy"** button to generate the KiCad code.  
   The code will be automatically copied to the clipboard, ready to be pasted into Eeschema.

---

## Contributions

Contributions are welcome. If you encounter any issues or have suggestions for improvements, please feel free to open an issue or submit a pull request.

---

## License

This project is licensed under the [MIT License](LICENSE).

---
