import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import requests
import json
import math
import time
from threading import Thread
import os

class PenPlotterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pen Plotter Drawing App - Klipper API")
        self.root.geometry("1000x800")
        
        # 描画データ
        self.drawing_paths = []  # [[x1,y1,pen_down], [x2,y2,pen_down], ...]
        self.current_path = []
        self.canvas_objects = []  # キャンバス上の描画オブジェクトを追跡
        self.is_drawing = False
        self.last_x = 0
        self.last_y = 0
        
        # Klipper API設定
        self.klipper_host = tk.StringVar(value="192.168.1.100")
        self.klipper_port = tk.StringVar(value="7125")
        
        # ペンプロッタ設定
        self.bed_size_x = tk.DoubleVar(value=100.0)  # mm
        self.bed_size_y = tk.DoubleVar(value=148.0)  # mm
        self.pen_up_z = tk.DoubleVar(value=2.0)      # mm
        self.pen_down_z = tk.DoubleVar(value=0.0)    # mm
        self.speed = tk.IntVar(value=6000)           # mm/min
        
        # 描画設定 - 100:148の比率でキャンバスサイズを計算
        self.canvas_width = 400
        self.canvas_height = int(400 * 148 / 100)  # 592ピクセル
        self.pen_color = "#000000"
        self.pen_width = 2
        
        self.setup_ui()
        
    def setup_ui(self):
        # メインフレーム
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左側：設定パネル
        settings_frame = ttk.LabelFrame(main_frame, text="設定", width=350)
        settings_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        settings_frame.pack_propagate(False)
        
        # Klipper API設定
        api_frame = ttk.LabelFrame(settings_frame, text="Klipper API設定")
        api_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(api_frame, text="ホスト:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(api_frame, textvariable=self.klipper_host, width=20).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(api_frame, text="ポート:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(api_frame, textvariable=self.klipper_port, width=20).grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Button(api_frame, text="接続テスト", command=self.test_connection).grid(row=2, column=0, columnspan=2, pady=5)
        
        # プロッタ設定
        plotter_frame = ttk.LabelFrame(settings_frame, text="プロッタ設定")
        plotter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(plotter_frame, text="ベッドサイズ X (mm):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(plotter_frame, textvariable=self.bed_size_x, width=10).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(plotter_frame, text="ベッドサイズ Y (mm):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(plotter_frame, textvariable=self.bed_size_y, width=10).grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Label(plotter_frame, text="ペン上昇 Z (mm):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(plotter_frame, textvariable=self.pen_up_z, width=10).grid(row=2, column=1, padx=5, pady=2)
        
        ttk.Label(plotter_frame, text="ペン下降 Z (mm):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(plotter_frame, textvariable=self.pen_down_z, width=10).grid(row=3, column=1, padx=5, pady=2)
        
        # スピード設定フレーム
        speed_frame = ttk.LabelFrame(settings_frame, text="スピード設定")
        speed_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(speed_frame, text="スピード (mm/分):").pack(anchor=tk.W, padx=5, pady=2)
        
        # スピードスライダー
        speed_slider = ttk.Scale(speed_frame, from_=100, to=10000, orient=tk.HORIZONTAL,
                                variable=self.speed, command=self.update_speed_display)
        speed_slider.pack(fill=tk.X, padx=5, pady=2)
        
        # スピード値表示テキストボックス
        self.speed_entry = ttk.Entry(speed_frame, textvariable=self.speed, width=10, justify=tk.CENTER)
        self.speed_entry.pack(pady=2)
        self.speed_entry.bind('<Return>', self.update_speed_from_entry)
        
        # 描画設定
        draw_frame = ttk.LabelFrame(settings_frame, text="描画設定")
        draw_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(draw_frame, text="線の太さ:").pack()
        width_scale = ttk.Scale(draw_frame, from_=1, to=10, orient=tk.HORIZONTAL, 
                               command=self.update_pen_width)
        width_scale.set(self.pen_width)
        width_scale.pack(fill=tk.X, padx=5)
        
        # コントロールボタン
        control_frame = ttk.LabelFrame(settings_frame, text="コントロール")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="クリア", command=self.clear_canvas).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="UNDO", command=self.undo_last_stroke).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="GCode保存", command=self.save_gcode).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="プロット実行", command=self.execute_plot).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="ホーム", command=self.home_printer).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="緊急停止", command=self.emergency_stop).pack(fill=tk.X, pady=2)
        
        # 右側：描画キャンバス
        canvas_frame = ttk.LabelFrame(main_frame, text="描画エリア")
        canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, width=self.canvas_width, height=self.canvas_height, 
                               bg="white", cursor="crosshair")
        self.canvas.pack(padx=10, pady=10)
        
        # マウスイベント
        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", self.end_draw)
        
        # 生成されたGCode
        self.gcode_lines = []
        
    def update_speed_display(self, value):
        """スピードスライダーの値が変更された時の処理"""
        self.speed.set(int(float(value)))
        
    def update_speed_from_entry(self, event):
        """テキストボックスからスピード値を更新"""
        try:
            speed_value = int(self.speed_entry.get())
            if 100 <= speed_value <= 10000:
                self.speed.set(speed_value)
            else:
                messagebox.showwarning("警告", "スピードは100-10000の範囲で入力してください")
                self.speed_entry.delete(0, tk.END)
                self.speed_entry.insert(0, str(self.speed.get()))
        except ValueError:
            messagebox.showwarning("警告", "数値を入力してください")
            self.speed_entry.delete(0, tk.END)
            self.speed_entry.insert(0, str(self.speed.get()))
        color = colorchooser.askcolor(title="ペン色を選択")[1]
        if color:
            self.pen_color = color
            
    def update_pen_width(self, value):
        self.pen_width = int(float(value))
        
    def start_draw(self, event):
        self.is_drawing = True
        self.last_x = event.x
        self.last_y = event.y
        self.current_path = [(event.x, event.y, True)]  # True = pen down
        self.current_canvas_objects = []  # 現在のストロークのキャンバスオブジェクト
        
    def draw(self, event):
        if self.is_drawing:
            line_id = self.canvas.create_line(self.last_x, self.last_y, event.x, event.y,
                                  fill=self.pen_color, width=self.pen_width, capstyle=tk.ROUND)
            self.current_canvas_objects.append(line_id)
            self.current_path.append((event.x, event.y, True))
            self.last_x = event.x
            self.last_y = event.y
            
    def end_draw(self, event):
        if self.is_drawing:
            self.is_drawing = False
            if self.current_path:
                self.drawing_paths.append(self.current_path.copy())
                self.canvas_objects.append(self.current_canvas_objects.copy())
                self.current_path = []
                self.current_canvas_objects = []
                
    def clear_canvas(self):
        self.canvas.delete("all")
        self.drawing_paths = []
        self.canvas_objects = []
        self.gcode_lines = []
        
    def undo_last_stroke(self):
        """直前の描画ストロークを削除"""
        if self.drawing_paths and self.canvas_objects:
            # 最後のストロークを削除
            self.drawing_paths.pop()
            last_objects = self.canvas_objects.pop()
            
            # キャンバスから対応する線を削除
            for obj_id in last_objects:
                self.canvas.delete(obj_id)
        
    def canvas_to_plotter_coords(self, canvas_x, canvas_y):
        """キャンバス座標をプロッタ座標に変換"""
        # キャンバス座標をプロッタベッド座標に変換
        plotter_x = (canvas_x / self.canvas_width) * self.bed_size_x.get()
        plotter_y = ((self.canvas_height - canvas_y) / self.canvas_height) * self.bed_size_y.get()
        return plotter_x, plotter_y
        
    def generate_gcode(self):
        if not self.drawing_paths:
            messagebox.showwarning("警告", "描画データがありません")
            return
            
        self.gcode_lines = []
        
        # GCodeヘッダー
        self.gcode_lines.extend([
            "; Generated by Pen Plotter App",
            "; " + time.strftime("%Y-%m-%d %H:%M:%S"),
            "G28 ; Home all axes",
            "G90 ; Absolute positioning",
            "G21 ; Units in millimeters",
            f"G1 Z{self.pen_up_z.get()} F{self.speed.get()} ; Pen up",
            "M5 ; Pen up",
            ""
        ])
        
        # 描画パスを処理
        for path in self.drawing_paths:
            if not path:
                continue
                
            # パスの最初の点に移動（ペンアップ）
            first_x, first_y = self.canvas_to_plotter_coords(path[0][0], path[0][1])
            self.gcode_lines.append(f"G1 X{first_x:.3f} Y{first_y:.3f} F{self.speed.get()} ; Move to start")
            self.gcode_lines.append(f"G1 Z{self.pen_down_z.get()} F{self.speed.get()} ; Pen down")
            self.gcode_lines.append("M3 ; Pen down")
            
            # パスを描画
            for point in path[1:]:
                x, y = self.canvas_to_plotter_coords(point[0], point[1])
                self.gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f} F{self.speed.get()}")
                
            # ペンアップ
            self.gcode_lines.append(f"G1 Z{self.pen_up_z.get()} F{self.speed.get()} ; Pen up")
            self.gcode_lines.append("M5 ; Pen up")
            self.gcode_lines.append("")
            
        # GCodeフッター
        self.gcode_lines.extend([
            "G1 X0 Y0 F{} ; Return to origin".format(self.speed.get()),
            "M5 ; Pen up",
            "M02 ; End of program",
            "; End of program"
        ])
        
        # テキストエリアに表示（削除）
        messagebox.showinfo("完了", f"GCodeを生成しました。\n総行数: {len(self.gcode_lines)}")
        
    def save_gcode(self):
        if not self.drawing_paths:
            messagebox.showwarning("警告", "描画データがありません")
            return
            
        # GCodeを生成
        self.generate_gcode()
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".gcode",
            filetypes=[("GCode files", "*.gcode"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("\n".join(self.gcode_lines))
                messagebox.showinfo("保存完了", f"GCodeを保存しました:\n{filename}")
            except Exception as e:
                messagebox.showerror("エラー", f"保存に失敗しました:\n{str(e)}")
                
    def test_connection(self):
        def test():
            try:
                url = f"http://{self.klipper_host.get()}:{self.klipper_port.get()}/printer/info"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    messagebox.showinfo("接続成功", f"Klipperに接続しました\n状態: {data.get('result', {}).get('state', 'Unknown')}")
                else:
                    messagebox.showerror("接続エラー", f"HTTP {response.status_code}")
            except Exception as e:
                messagebox.showerror("接続エラー", f"接続に失敗しました:\n{str(e)}")
                
        Thread(target=test, daemon=True).start()
        
    def send_gcode_command(self, command):
        """Klipper APIにGCodeコマンドを送信"""
        try:
            url = f"http://{self.klipper_host.get()}:{self.klipper_port.get()}/printer/gcode/script"
            data = {"script": command}
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            messagebox.showerror("エラー", f"コマンド送信に失敗しました:\n{str(e)}")
            return False
            
    def execute_plot(self):
        if not self.drawing_paths:
            messagebox.showwarning("警告", "描画データがありません")
            return
            
        # GCodeを生成
        self.generate_gcode()
            
        def plot():
            try:
                total_lines = len(self.gcode_lines)
                progress_window = tk.Toplevel(self.root)
                progress_window.title("プロット実行中")
                progress_window.geometry("400x150")
                progress_window.transient(self.root)
                progress_window.grab_set()
                
                ttk.Label(progress_window, text="プロットを実行中...").pack(pady=10)
                
                progress_var = tk.DoubleVar()
                progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
                progress_bar.pack(fill=tk.X, padx=20, pady=10)
                
                status_label = ttk.Label(progress_window, text="")
                status_label.pack()
                
                stop_button = ttk.Button(progress_window, text="停止", 
                                       command=lambda: self.emergency_stop())
                stop_button.pack(pady=10)
                
                for i, line in enumerate(self.gcode_lines):
                    if line.strip() and not line.startswith(';'):
                        status_label.config(text=f"実行中: {line[:50]}...")
                        if not self.send_gcode_command(line.strip()):
                            messagebox.showerror("エラー", f"コマンド実行に失敗しました:\n{line}")
                            break
                        time.sleep(0.1)  # 少し待機
                        
                    progress = (i + 1) / total_lines * 100
                    progress_var.set(progress)
                    progress_window.update()
                    
                progress_window.destroy()
                messagebox.showinfo("完了", "プロットが完了しました")
                
            except Exception as e:
                messagebox.showerror("エラー", f"プロット実行中にエラーが発生しました:\n{str(e)}")
                
        Thread(target=plot, daemon=True).start()
        
    def home_printer(self):
        if self.send_gcode_command("G28"):
            messagebox.showinfo("完了", "ホーミングを実行しました")
            
    def emergency_stop(self):
        if self.send_gcode_command("M112"):
            messagebox.showinfo("完了", "緊急停止を実行しました")

def main():
    root = tk.Tk()
    app = PenPlotterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()