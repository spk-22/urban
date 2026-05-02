import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import requests

# =========================
# CONFIG
# =========================
FLASK_API_URL = "http://127.0.0.1:5000/upload-xml"


class XMLUploaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Bangalore Utility Network XML Processor")
        self.root.geometry("750x550")
        self.root.resizable(False, False)

        self.file_path = None

        # =========================
        # TITLE
        # =========================
        title = tk.Label(
            root,
            text="Infrastructure XML to Excel Converter",
            font=("Arial", 18, "bold")
        )
        title.pack(pady=20)

        # =========================
        # FILE SELECT
        # =========================
        file_frame = tk.Frame(root)
        file_frame.pack(pady=15)

        self.file_label = tk.Label(
            file_frame,
            text="No file selected",
            width=65,
            anchor="w",
            relief="sunken"
        )
        self.file_label.pack(side=tk.LEFT, padx=10)

        browse_btn = tk.Button(
            file_frame,
            text="Browse XML File",
            command=self.browse_file,
            bg="#4CAF50",
            fg="white",
            width=18
        )
        browse_btn.pack(side=tk.LEFT)

        # =========================
        # TYPE SELECTOR
        # =========================
        type_frame = tk.Frame(root)
        type_frame.pack(pady=20)

        tk.Label(
            type_frame,
            text="Select Infrastructure Type:",
            font=("Arial", 12)
        ).pack(side=tk.LEFT, padx=10)

        self.choice_var = tk.StringVar()

        dropdown = ttk.Combobox(
            type_frame,
            textvariable=self.choice_var,
            state="readonly",
            width=25,
            values=[
                "1 - Power",
                "2 - Water",
                "3 - Road"
            ]
        )
        dropdown.current(0)
        dropdown.pack(side=tk.LEFT)

        # =========================
        # PROCESS BUTTON
        # =========================
        process_btn = tk.Button(
            root,
            text="Upload and Process",
            command=self.process_file,
            bg="#2196F3",
            fg="white",
            font=("Arial", 12, "bold"),
            width=28,
            height=2
        )
        process_btn.pack(pady=20)

        # =========================
        # OUTPUT DISPLAY
        # =========================
        self.output_box = tk.Text(
            root,
            height=16,
            width=90,
            wrap=tk.WORD
        )
        self.output_box.pack(padx=15, pady=15)

    # =========================
    # FILE BROWSER
    # =========================
    def browse_file(self):
        selected_file = filedialog.askopenfilename(
            title="Select XML/OSM File",
            filetypes=[("OSM/XML Files", "*.osm *.xml")]
        )

        if selected_file:
            self.file_path = selected_file
            self.file_label.config(text=selected_file)

    # =========================
    # PROCESS FILE
    # =========================
    def process_file(self):
        if not self.file_path:
            messagebox.showerror(
                "Error",
                "Please select an XML/OSM file first."
            )
            return

        try:
            # Extract numeric choice (1/2/3)
            selected_choice = self.choice_var.get()[0]

            with open(self.file_path, "rb") as file:
                files = {
                    "file": file
                }

                data = {
                    "choice": selected_choice
                }

                response = requests.post(
                    FLASK_API_URL,
                    files=files,
                    data=data
                )

            self.output_box.delete(1.0, tk.END)

            # =========================
            # SUCCESS
            # =========================
            if response.status_code == 200:
                result = response.json()

                if result["file_type"] == "road":
                    infra_details = (
                        "Road Network Details:\n"
                        "- Traffic signals\n"
                        "- Junctions\n"
                        "- Crossings\n"
                        "- Road node categories\n"
                        "- Highway classification\n"
                        "- Critical traffic points\n"
                    )
                elif result["file_type"] == "water":
                    infra_details = (
                        "Water Infrastructure Details:\n"
                        "- Reservoirs\n"
                        "- Water tanks\n"
                        "- Water treatment plants\n"
                        "- Water works\n"
                    )
                else:
                    infra_details = (
                        "Power Infrastructure Details:\n"
                        "- Substations\n"
                        "- Stations\n"
                        "- Transformers\n"
                        "- Plants\n"
                        "- Generators\n"
                    )

                output = (
                    f"PROCESS SUCCESSFUL\n\n"
                    f"Message: {result['message']}\n"
                    f"Infrastructure Type: {result['file_type'].capitalize()}\n"
                    f"Rows Extracted: {result['rows_extracted']}\n\n"
                    f"{infra_details}\n"
                    f"Excel Output Saved At:\n"
                    f"{result['excel_output']}\n"
                )

                self.output_box.insert(tk.END, output)

                messagebox.showinfo(
                    "Success",
                    f"{result['file_type'].capitalize()} file processed successfully!"
                )

            # =========================
            # FAILURE
            # =========================
            else:
                error_data = response.json()

                self.output_box.insert(
                    tk.END,
                    f"PROCESS FAILED\n\n{error_data}"
                )

                messagebox.showerror(
                    "Error",
                    str(error_data)
                )

        # =========================
        # BACKEND NOT RUNNING
        # =========================
        except requests.exceptions.ConnectionError:
            messagebox.showerror(
                "Backend Not Running",
                "Start Flask backend first using:\npython app.py"
            )

        # =========================
        # OTHER ERRORS
        # =========================
        except Exception as e:
            messagebox.showerror(
                "Unexpected Error",
                str(e)
            )


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    root = tk.Tk()
    gui = XMLUploaderGUI(root)
    root.mainloop()