import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image
import piexif
import piexif.helper
import os
import concurrent.futures

def convertWebPtoPNG(input_path, output_path):
    with Image.open(input_path) as img:
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
        else:
            img = img.convert('RGB')
        exif = img.info.get('exif')
        img.save(output_path, 'PNG', exif=exif)

def process_image(filename, src_path, dst_path, target_format, islossless):
    path = os.path.join(src_path, filename)
    image = Image.open(path)
    items = image.info or {}
    geninfo = items.pop('parameters', None)
    
    if "exif" in items:
        exif = piexif.load(items["exif"])
        exif_comment = (exif or {}).get("Exif", {}).get(piexif.ExifIFD.UserComment, b'')
        try:
            exif_comment = piexif.helper.UserComment.load(exif_comment)
        except ValueError:
            exif_comment = exif_comment.decode('utf8', errors="ignore")
        if exif_comment:
            items['exif comment'] = exif_comment
            geninfo = exif_comment
        for field in ['jfif', 'jfif_version', 'jfif_unit', 'jfif_density', 'dpi', 'exif', 'loop', 'background', 'timestamp', 'duration']:
            items.pop(field, None)
    
    exif_bytes = piexif.dump({
        "Exif": {
            piexif.ExifIFD.UserComment: piexif.helper.UserComment.dump(geninfo or "", encoding="unicode")
        }
    })

    # 假設背景顏色為白色
    background_color = (255, 255, 255)

    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        if target_format.upper() == 'JPG':
            # 創建一個白色背景的圖像
            background = Image.new('RGB', image.size, background_color)
            # 合併圖像以去除透明度
            background.paste(image, mask=image.split()[3])  # 3 是 alpha 通道的索引
            converted_image = background
        else:
            converted_image = image.convert('RGBA')
    else:
        converted_image = image.convert('RGB')
    
    pre, ext = os.path.splitext(filename)
    dstpath = os.path.join(dst_path, pre + f'.{target_format.lower()}')
    
    if target_format.upper() == 'WEBP':
        if islossless:
            converted_image.save(dstpath, 'WEBP', lossless=True)
        else:
            converted_image.save(dstpath, 'WEBP', lossless=False, quality=95)
    elif target_format.upper() == 'JPG':
        converted_image.save(dstpath, 'JPEG', quality=95, optimize=True)
    else:
        raise ValueError(f"Unsupported target format: {target_format}")
    
    piexif.insert(exif_bytes, dstpath)

def convertPNGtoWebP(filename, src_path, dst_path, islossless):
    process_image(filename, src_path, dst_path, 'WEBP', islossless)

def convertPNGtoJPEG(filename, src_path, dst_path, islossless):
    process_image(filename, src_path, dst_path, 'JPG', islossless)

# 定义一个函数来打开文件夹选择对话框并获取路径
def open_file_dialog():
    # 清空 finish 標籤的文本
    finish.config(text="")

    # 检查是否已经存在上次选择的路径，如果存在则使用它
    initial_dir = os.path.expanduser("~/")  # 默认使用用户的主目录作为初始目录
    if hasattr(open_file_dialog, 'last_path'):
        initial_dir = open_file_dialog.last_path

    # 打开文件选择对话框
    global folder_path
    file_path = filedialog.askopenfilename(
        initialdir=initial_dir,
        title="選擇一個圖像檔案",
        filetypes=[("圖像檔案", "*.png *.webp"), ("所有文件", "*.*")]
    )

    if file_path:  # 如果用户选择了文件
        # 获取所选文件的文件夹路径
        folder_path = os.path.dirname(file_path)
        # 更新文本框显示选择的文件夹路径
        path_label.config(text=folder_path)
        # 记住这个路径，以便下次使用
        open_file_dialog.last_path = folder_path

    return folder_path

def get_all_files(folder_path, source_ext, include_subfolders):
    all_files = []
    if include_subfolders:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(f'.{source_ext}'):
                    all_files.append(os.path.join(root, file))
    else:
        for file in os.listdir(folder_path):
            if file.lower().endswith(f'.{source_ext}'):
                all_files.append(os.path.join(folder_path, file))
    return all_files

def process_files(files, group_id, source_ext, target_ext, conversion_type, target_folder, move_files, delete_source, islossless, include_subfolders):
    for file_path in files:
        filename = os.path.basename(file_path)
        folder_path = os.path.dirname(file_path)
        if filename.lower().endswith(f'.{source_ext}'):
            # 構建源文件和目標文件的完整路徑
            source_file = file_path
            if include_subfolders:
                relative_path = os.path.relpath(folder_path, start=folder_path)
                new_target_folder = os.path.join(target_folder, relative_path) if move_files else folder_path
                os.makedirs(new_target_folder, exist_ok=True)
                target_file = os.path.join(new_target_folder, os.path.splitext(filename)[0] + f'.{target_ext}')
            else:
                target_file = os.path.join(folder_path, os.path.splitext(filename)[0] + f'.{target_ext}')
            
            try:
                # 根據選擇的轉換類型執行相應的轉換函數
                if conversion_type == 'webp → png':
                    convertWebPtoPNG(source_file, target_file)
                elif conversion_type == 'png → webp':
                    convertPNGtoWebP(filename, folder_path, os.path.dirname(target_file), islossless)
                elif conversion_type == 'png → jpg':
                    convertPNGtoJPEG(filename, folder_path, os.path.dirname(target_file), islossless)
                
                # 如果選擇了移動轉換後的圖片，則將其移動到指定文件夾
                if move_files and os.path.exists(target_folder) and not include_subfolders:
                    os.rename(target_file, os.path.join(target_folder, os.path.basename(target_file)))
                
                # 如果選擇了刪除原圖，則刪除原圖
                if delete_source:
                    os.remove(source_file)
                
            except Exception as e:
                print(f"轉換文件 {filename} 時發生錯誤: {str(e)}")

def convert_images(folder_path):
    # 獲取選擇的轉換選項
    conversion_type = selected.get()
    source_ext, target_ext = conversion_type.split(' → ')
    
    # 獲取用戶設置的目標文件夾名稱（如果有）
    target_folder_name = entry.get().strip()
    target_folder = os.path.join(folder_path, target_folder_name)
    
    # 如果選擇了移動轉換後的圖片，確保目標文件夾存在
    if var1.get() and not os.path.exists(target_folder):
        os.makedirs(target_folder)

    # 讀取目錄及其子目錄下所有特定副檔名的文件
    all_files = get_all_files(folder_path, source_ext, var3.get())

    if var4.get():  # 如果選擇了分組執行
        # 分成四組
        groups = [[] for _ in range(4)]
        for i, file in enumerate(all_files):
            groups[i % 4].append(file)

        # 同時執行四個步驟
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(
                process_files, 
                group, 
                i, 
                source_ext, 
                target_ext, 
                conversion_type, 
                target_folder, 
                var1.get(),  # move_files
                var2.get(),  # delete_source
                lossless_var.get(),  # islossless
                var3.get()  # include_subfolders
            ) for i, group in enumerate(groups)]
            concurrent.futures.wait(futures)
    else:  # 如果沒有選擇分組執行
        # 直接處理所有文件
        process_files(
            all_files, 
            0, 
            source_ext, 
            target_ext, 
            conversion_type, 
            target_folder, 
            var1.get(),  # move_files
            var2.get(),  # delete_source
            lossless_var.get(),  # islossless
            var3.get()  # include_subfolders
        )
    
    # 更新UI或彈出消息框通知用戶轉換完成
    finish.config(text="完成", foreground="red")
    window.after(10000, lambda: disapper(finish))

def disapper(label):
    label.config(text="")  # 最後將文字清空

if __name__ == '__main__':
    window = tk.Tk()
    # 配置 ttk 主題
    style = ttk.Style(window)
    # 您可以選擇一個現有的主題，這取決於您的系統和安裝的 ttk 主題
    # 使用 style.theme_names() 查看可用主題
    # print(style.theme_names())
    style.theme_use('vista')  # 更改為您想要的主題
    window.title("pweg")
    window.geometry("600x450")  # 宽度x高度

    # 設定自定義樣式的字型
    myFont = ("Microsoft JhengHei", 14)

    # 創建自定義樣式
    style.configure("My.TButton", font=myFont)
    style.configure("My.TLabel", font=myFont)
    style.configure("My.TCheckbutton", font=myFont)

    # 创建一个按钮，点击时会触发open_folder_dialog函数
    choose_button = ttk.Button(window, text="選擇圖像以指定路徑", style="My.TButton", command=open_file_dialog)
    choose_button.pack(pady=(30, 0))

    # 创建一个标签用来显示文件夹路径
    path_label = ttk.Label(window, text="", style="My.TLabel")
    path_label.pack(pady=10)



    # 变量，用于存储勾选框的状态
    var1 = tk.BooleanVar()
    var2 = tk.BooleanVar()
    var3 = tk.BooleanVar()
    var4 = tk.BooleanVar()
    var4.set(True)
    # 創建一個布爾型變量來追踪 "lossless" 勾選框的選中狀態
    lossless_var = tk.BooleanVar()
    lossless_var.set(True)  # 將 lossless_var 的值設置為 True，使勾選框一開始就處於勾選狀態

    frame = tk.Frame(window)
    frame.pack(padx=10, pady=10)

    frame2 = ttk.Frame(frame)
    frame2.pack(side="top", fill="x", padx=20, expand=True)

    # 定义下拉菜单的选项
    options = ['png → webp', 'png → jpg', 'webp → png']

    # 创建一个变量来存储下拉菜单的选择
    selected = tk.StringVar()
    selected.set(options[0])  # 设置默认选项

    # 创建下拉菜单
    option_menu = ttk.Combobox(frame2, textvariable=selected, values=options, state="readonly", font=myFont)
    window.option_add('*TCombobox*Listbox.font', myFont)
    option_menu.pack(side="left", anchor="n")

    # 將 lossless_check 放入 window
    lossless_check = ttk.Checkbutton(frame2, text="無損壓縮", style="My.TCheckbutton", variable=lossless_var)

    # 定義一個函數來根據 Combobox 的選擇顯示或隱藏 "lossless" 勾選框
    def update_lossless_visibility(event):
        if selected.get() == "png → webp":
            lossless_check.pack(side="left", anchor="n", padx=(10, 0))
        else:
            lossless_check.pack_forget()

    # 為 Combobox 添加事件綁定，當選擇改變時調用 update_lossless_visibility 函數
    option_menu.bind("<<ComboboxSelected>>", update_lossless_visibility)

    # 初始時調用一次函數以設置正確的顯示狀態
    update_lossless_visibility(None)

    # 在 frame 內創建一個新的框架來容納 check1, entry 和 Label，以保持它們在同一行
    frame3 = ttk.Frame(frame)
    frame3.pack(side="top", fill="x", pady=(10, 0), expand=True)

    # 创建勾选框1
    check1 = ttk.Checkbutton(frame3, text="轉換後的圖像移至當前路徑的資料夾: ", style="My.TCheckbutton", variable=var1)
    check1.pack(side="left", anchor="n")

    entry = ttk.Entry(frame3, width=10, font=myFont)
    entry.pack(side="left", anchor="n")

    ttk.Label(frame, text="(若沒有此名稱會自動建立)", style="My.TLabel").pack(side="top", anchor="w", padx=20)

    # 创建勾选框2
    check2 = ttk.Checkbutton(frame, text="刪除轉換前的圖像", style="My.TCheckbutton", variable=var2)
    check2.pack(side="top", anchor="w", pady=(10, 0))

    # 创建勾选框3
    check3 = ttk.Checkbutton(frame, text="包含子資料夾", style="My.TCheckbutton", variable=var3)
    check3.pack(side="top", anchor="w", pady=(10, 0))

    # 创建勾选框4
    check4 = ttk.Checkbutton(frame, text="分組執行", style="My.TCheckbutton", variable=var4)
    check4.pack(side="top", anchor="w", pady=(10, 0))

    def on_var3_change(*args):
        if var3.get():
            var1.set(False)
            check1.state(['disabled'])  # 將 check1 設置為不可用
            entry.state(['disabled']) 
        else:
            check1.state(['!disabled'])  # 將 check1 設置為可用
            entry.state(['!disabled'])

    # 為 var3 添加 trace
    var3.trace_add('write', on_var3_change)

    finish = ttk.Label(window, text="", style="My.TLabel")

    convert_button = ttk.Button(window, text="轉換所有圖片", style="My.TButton", command=lambda: convert_images(folder_path))
    convert_button.pack()

    finish.pack(pady=10)

    window.mainloop()