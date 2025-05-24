import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import json
import math
import time
from threading import Thread
import os
import re

class PenPlotterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pen Plotter Drawing App - Klipper API")
        self.root.geometry("1280x800")  # 画面サイズを1280x800に変更
        
        # 描画データ
        self.drawing_paths = []  # [[x1,y1,pen_down], [x2,y2,pen_down], ...]
        self.current_path = []
        self.canvas_objects = []  # キャンバス上の描画オブジェクトを追跡
        self.is_drawing = False
        self.last_x = 0
        self.last_y = 0
        
        # Klipper API設定
        self.klipper_host = tk.StringVar(value="192.168.1.208")
        self.klipper_port = tk.StringVar(value="80")
        
        # ペンプロッタ設定
        self.bed_size_x = tk.DoubleVar(value=100.0)  # mm
        self.bed_size_y = tk.DoubleVar(value=148.0)  # mm
        self.speed = tk.IntVar(value=6000)           # mm/min デフォルトF6000
        
        # 描画設定 - 100:148の比率でキャンバスサイズを計算（大きくする）
        self.canvas_width = 500
        self.canvas_height = int(500 * 148 / 100)  # 740ピクセル
        self.pen_color = "#000000"  # 固定色（黒）
        self.pen_width = 1  # デフォルト線の太さを1に変更
        
        self.setup_ui()
        
    def setup_ui(self):
        # メインフレーム
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左側：設定パネル
        settings_frame = ttk.LabelFrame(main_frame, text="設定", width=400)  # 幅を広げる
        settings_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        settings_frame.pack_propagate(False)
        
        # Klipper API設定
        api_frame = ttk.LabelFrame(settings_frame, text="Klipper API設定")
        api_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(api_frame, text="ホスト:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(api_frame, textvariable=self.klipper_host, width=15).grid(row=0, column=1, padx=5, pady=2)
        # 接続テストボタンをホストIPの右側に配置
        ttk.Button(api_frame, text="接続テスト", command=self.test_connection).grid(row=0, column=2, padx=5, pady=2)
        
        ttk.Label(api_frame, text="ポート:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(api_frame, textvariable=self.klipper_port, width=15).grid(row=1, column=1, padx=5, pady=2)
        
        # プロッタ設定
        plotter_frame = ttk.LabelFrame(settings_frame, text="プロッタ設定")
        plotter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(plotter_frame, text="ベッドサイズ X (mm):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(plotter_frame, textvariable=self.bed_size_x, width=10).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(plotter_frame, text="ベッドサイズ Y (mm):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(plotter_frame, textvariable=self.bed_size_y, width=10).grid(row=1, column=1, padx=5, pady=2)
        
        # スピード設定フレーム
        speed_frame = ttk.LabelFrame(settings_frame, text="スピード設定")
        speed_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(speed_frame, text="スピード (mm/分):").pack(anchor=tk.W, padx=5, pady=2)
        
        # スピードスライダー
        speed_slider = ttk.Scale(speed_frame, from_=1000, to=12000, orient=tk.HORIZONTAL,
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
        width_scale.set(self.pen_width)  # デフォルトを1に設定
        width_scale.pack(fill=tk.X, padx=5)
        
        # コントロールボタン
        control_frame = ttk.LabelFrame(settings_frame, text="コントロール")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="クリア", command=self.clear_canvas).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="UNDO", command=self.undo_last_stroke).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="GCode保存", command=self.save_gcode).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="GCodeロード", command=self.load_gcode).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="プロット実行", command=self.execute_plot).pack(fill=tk.X, pady=2)
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
            if 1000 <= speed_value <= 12000:
                self.speed.set(speed_value)
            else:
                messagebox.showwarning("警告", "スピードは1000-12000の範囲で入力してください")
                self.speed_entry.delete(0, tk.END)
                self.speed_entry.insert(0, str(self.speed.get()))
        except ValueError:
            messagebox.showwarning("警告", "数値を入力してください")
            self.speed_entry.delete(0, tk.END)
            self.speed_entry.insert(0, str(self.speed.get()))
            
    def update_pen_width(self, value):
        self.pen_width = int(float(value))
        
    def start_draw(self, event):
        # キャンバス範囲内での描画開始のみ許可
        x = max(0, min(event.x, self.canvas_width))
        y = max(0, min(event.y, self.canvas_height))
        
        self.is_drawing = True
        self.last_x = x
        self.last_y = y
        self.current_path = [(x, y, True)]  # True = pen down
        self.current_canvas_objects = []  # 現在のストロークのキャンバスオブジェクト
        
    def draw(self, event):
        if self.is_drawing:
            # キャンバス範囲内での描画のみ許可
            x = max(0, min(event.x, self.canvas_width))
            y = max(0, min(event.y, self.canvas_height))
            
            line_id = self.canvas.create_line(self.last_x, self.last_y, x, y,
                                  fill=self.pen_color, width=self.pen_width, capstyle=tk.ROUND)
            self.current_canvas_objects.append(line_id)
            self.current_path.append((x, y, True))
            self.last_x = x
            self.last_y = y
            
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
        """キャンバス座標をプロッタ座標に変換（範囲制限付き）"""
        # キャンバス座標をプロッタベッド座標に変換
        plotter_x = (canvas_x / self.canvas_width) * self.bed_size_x.get()
        plotter_y = ((self.canvas_height - canvas_y) / self.canvas_height) * self.bed_size_y.get()
        
        # 座標を描画エリア範囲内に制限
        plotter_x = max(0, min(plotter_x, self.bed_size_x.get()))
        plotter_y = max(0, min(plotter_y, self.bed_size_y.get()))
        
        return plotter_x, plotter_y
        
    def plotter_to_canvas_coords(self, plotter_x, plotter_y):
        """プロッタ座標をキャンバス座標に変換"""
        canvas_x = (plotter_x / self.bed_size_x.get()) * self.canvas_width
        canvas_y = self.canvas_height - (plotter_y / self.bed_size_y.get()) * self.canvas_height
        return canvas_x, canvas_y
        
    def generate_gcode(self):
        if not self.drawing_paths:
            messagebox.showwarning("警告", "描画データがありません")
            return
            
        self.gcode_lines = []
        
        # GCodeヘッダー
        self.gcode_lines.extend([
            "; Generated by Pen Plotter App",
            "; " + time.strftime("%Y-%m-%d %H:%M:%S"),
            f"; Bed Size: X{self.bed_size_x.get():.1f}mm Y{self.bed_size_y.get():.1f}mm",
            "G28 ; Home all axes",
            "G90 ; Absolute positioning",
            "G21 ; Units in millimeters",
            "M5 ; Pen up",
            ""
        ])
        
        # 描画パスを処理
        for path in self.drawing_paths:
            if not path:
                continue
                
            # パスの最初の点に移動（ペンアップ）
            first_x, first_y = self.canvas_to_plotter_coords(path[0][0], path[0][1])
            
            # 範囲チェック（追加の安全チェック）
            if not (0 <= first_x <= self.bed_size_x.get() and 0 <= first_y <= self.bed_size_y.get()):
                continue  # 範囲外の場合はこのパスをスキップ
                
            self.gcode_lines.append(f"G1 X{first_x:.3f} Y{first_y:.3f} F{self.speed.get()} ; Move to start")
            self.gcode_lines.append("M3 ; Pen down")
            
            # パスを描画
            for point in path[1:]:
                x, y = self.canvas_to_plotter_coords(point[0], point[1])
                
                # 各座標が範囲内であることを確認
                if 0 <= x <= self.bed_size_x.get() and 0 <= y <= self.bed_size_y.get():
                    self.gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f} F{self.speed.get()}")
                
            # ペンアップ
            self.gcode_lines.append("M5 ; Pen up")
            self.gcode_lines.append("")
            
        # GCodeフッター
        self.gcode_lines.extend([
        #    "G1 X0 Y0 F{} ; Return to origin".format(self.speed.get()),
            "M5 ; Pen up",
            "M02 ; End of program",
            "; End of program"
        ])
        
    def save_gcode(self):
        if not self.drawing_paths:
            messagebox.showwarning("警告", "描画データがありません")
            return
            
        # GCodeを生成（保存時に生成）
        self.generate_gcode()
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".gcode",
            filetypes=[("GCode files", "*.gcode"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("\n".join(self.gcode_lines))
                messagebox.showinfo("保存完了", f"GCodeを保存しました:\n{filename}\n総行数: {len(self.gcode_lines)}")
            except Exception as e:
                messagebox.showerror("エラー", f"保存に失敗しました:\n{str(e)}")
                
    def load_gcode(self):
        """GCodeファイルをロードして描画パスを復元"""
        filename = filedialog.askopenfilename(
            title="GCodeファイルを選択",
            filetypes=[("GCode files", "*.gcode"), ("All files", "*.*")]
        )
        
        if not filename:
            return
            
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                gcode_content = f.readlines()
                
            # 現在の描画をクリア
            self.clear_canvas()
            
            # GCodeから描画パスを復元
            self.parse_gcode_to_paths(gcode_content)
            
            # キャンバスに描画パスを表示
            self.draw_paths_on_canvas()
            
            messagebox.showinfo("ロード完了", f"GCodeをロードしました:\n{filename}\n描画パス数: {len(self.drawing_paths)}")
            
        except Exception as e:
            messagebox.showerror("エラー", f"GCodeのロードに失敗しました:\n{str(e)}")
    
    def parse_gcode_to_paths(self, gcode_lines):
        """GCodeから描画パスを解析（改善版）"""
        self.drawing_paths = []
        current_path = []
        pen_down = False
        current_x = 0.0
        current_y = 0.0
        
        for line in gcode_lines:
            line = line.strip()
            
            # コメント行と空行をスキップ
            if not line or line.startswith(';'):
                continue
                
            # 大文字に変換して統一
            line_upper = line.upper()
            
            # ペンダウンコマンドの検出（複数のパターンに対応）
            if any(cmd in line_upper for cmd in ['M3', 'M03']):
                # ペンダウン状態に変更
                if not pen_down:
                    pen_down = True
                    # 既存のパスがあれば保存
                    if current_path:
                        self.drawing_paths.append(current_path)
                    current_path = []
                    # 現在位置をパスの開始点として追加
                    canvas_x, canvas_y = self.plotter_to_canvas_coords(current_x, current_y)
                    # キャンバス範囲内に制限
                    canvas_x = max(0, min(canvas_x, self.canvas_width))
                    canvas_y = max(0, min(canvas_y, self.canvas_height))
                    current_path.append((canvas_x, canvas_y, True))
                
            # ペンアップコマンドの検出（複数のパターンに対応）
            elif any(cmd in line_upper for cmd in ['M5', 'M05']):
                if pen_down:
                    pen_down = False
                    # 現在のパスを保存
                    if current_path:
                        self.drawing_paths.append(current_path)
                        current_path = []
                    
            # 移動コマンドの処理（G00, G01, G1など）
            elif any(line_upper.startswith(cmd) for cmd in ['G00', 'G01', 'G0', 'G1']):
                # 座標を抽出
                new_x, new_y = self.parse_coordinates(line)
                
                # 座標が見つかった場合のみ更新
                if new_x is not None:
                    current_x = new_x
                if new_y is not None:
                    current_y = new_y
                    
                # ペンダウン状態の場合のみパスに追加
                if pen_down and (new_x is not None or new_y is not None):
                    canvas_x, canvas_y = self.plotter_to_canvas_coords(current_x, current_y)
                    # キャンバス範囲内に制限
                    canvas_x = max(0, min(canvas_x, self.canvas_width))
                    canvas_y = max(0, min(canvas_y, self.canvas_height))
                    current_path.append((canvas_x, canvas_y, True))
        
        # 最後のパスを保存
        if current_path:
            self.drawing_paths.append(current_path)
            
        print(f"解析完了: {len(self.drawing_paths)}個のパスが見つかりました")
    
    def parse_coordinates(self, line):
        """GCodeコマンドからX,Y座標を抽出（改善版）"""
        x_val = None
        y_val = None
        
        # 正規表現を使用してより確実に座標を抽出
        x_match = re.search(r'X([-+]?\d*\.?\d+)', line.upper())
        y_match = re.search(r'Y([-+]?\d*\.?\d+)', line.upper())
        
        if x_match:
            try:
                x_val = float(x_match.group(1))
            except ValueError:
                pass
                
        if y_match:
            try:
                y_val = float(y_match.group(1))
            except ValueError:
                pass
                    
        return x_val, y_val
    
    def draw_paths_on_canvas(self):
        """描画パスをキャンバスに表示"""
        self.canvas_objects = []
        
        for path in self.drawing_paths:
            if len(path) < 2:
                continue
                
            path_objects = []
            for i in range(len(path) - 1):
                x1, y1 = path[i][:2]
                x2, y2 = path[i + 1][:2]
                
                line_id = self.canvas.create_line(x1, y1, x2, y2,
                                      fill=self.pen_color, width=self.pen_width, capstyle=tk.ROUND)
                path_objects.append(line_id)
                
            self.canvas_objects.append(path_objects)
                
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
            response = requests.post(url, json=data, timeout=20)
            return response.status_code == 200
        except Exception as e:
            messagebox.showerror("エラー", f"コマンド送信に失敗しました:\n{str(e)}")
            return False
    
    def send_entire_gcode_at_once(self):
        """全てのGCodeを一度に送信（最高速）"""
        try:
            # コメント行と空行を除外してGCodeを結合
            filtered_commands = []
            for line in self.gcode_lines:
                line = line.strip()
                if line and not line.startswith(';'):
                    filtered_commands.append(line)
            
            # 全てのコマンドを一つの文字列に結合
            complete_script = "\n".join(filtered_commands)
            
            url = f"http://{self.klipper_host.get()}:{self.klipper_port.get()}/printer/gcode/script"
            data = {"script": complete_script}
            response = requests.post(url, json=data, timeout=300)  # 5分のタイムアウト
            return response.status_code == 200
            
        except Exception as e:
            messagebox.showerror("エラー", f"GCode一括送信に失敗しました:\n{str(e)}")
            return False
    
    def send_optimized_bulk_gcode(self):
        """最適化されたバッチ送信（バックアップ方式）"""
        try:
            # 大きなバッチサイズで高速化
            batch_size = 200  # バッチサイズを大幅増加
            total_lines = len(self.gcode_lines)
            
            # コメント行と空行を事前にフィルタリング
            filtered_commands = [line.strip() for line in self.gcode_lines 
                               if line.strip() and not line.strip().startswith(';')]
            
            for i in range(0, len(filtered_commands), batch_size):
                batch = filtered_commands[i:i+batch_size]
                bulk_script = "\n".join(batch)
                
                url = f"http://{self.klipper_host.get()}:{self.klipper_port.get()}/printer/gcode/script"
                data = {"script": bulk_script}
                response = requests.post(url, json=data, timeout=120)
                
                if response.status_code != 200:
                    return False
                    
                # 遅延を完全に削除
                # time.sleep(0) 
                
            return True
            
        except Exception as e:
            messagebox.showerror("エラー", f"最適化バッチ送信に失敗しました:\n{str(e)}")
            return False
            
    def execute_plot(self):
        if not self.drawing_paths and not self.gcode_lines:
            messagebox.showwarning("警告", "描画データまたはGCodeがありません")
            return
        
        # 描画データがある場合はGCodeを生成
        if self.drawing_paths and not self.gcode_lines:
            self.generate_gcode()
        
        # GCodeが空の場合は警告
        if not self.gcode_lines:
            messagebox.showwarning("警告", "実行するGCodeがありません")
            return
            
        def plot():
            try:
                progress_window = tk.Toplevel(self.root)
                progress_window.title("プロット実行中")
                progress_window.geometry("400x200")
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
                
                # まず一括送信を試行（最高速）
                status_label.config(text="全GCodeを一括送信中...")
                progress_var.set(10)
                progress_window.update()
                
                if self.send_entire_gcode_at_once():
                    progress_var.set(100)
                    progress_window.update()
                    time.sleep(0.5)  # UIの更新時間
                    progress_window.destroy()
                    messagebox.showinfo("完了", "プロットが完了しました（一括送信）")
                    return
                
                # 一括送信が失敗した場合は最適化バッチ送信
                status_label.config(text="最適化バッチ送信中...")
                progress_var.set(20)
                progress_window.update()
                
                if self.send_optimized_bulk_gcode():
                    progress_var.set(100)
                    progress_window.update()
                    time.sleep(0.5)
                    progress_window.destroy()
                    messagebox.showinfo("完了", "プロットが完了しました（最適化バッチ）")
                    return
                
                # 両方失敗した場合のエラー
                progress_window.destroy()
                messagebox.showerror("エラー", "全ての送信方式が失敗しました")
                
            except Exception as e:
                progress_window.destroy()
                messagebox.showerror("エラー", f"プロット実行中にエラーが発生しました:\n{str(e)}")
                                
        Thread(target=plot, daemon=True).start()
            
    def emergency_stop(self):
        if self.send_gcode_command("M112"):
            messagebox.showinfo("完了", "緊急停止を実行しました")

def main():
    root = tk.Tk()
    app = PenPlotterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()