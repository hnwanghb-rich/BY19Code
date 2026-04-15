import tkinter as tk
from tkinter import font

class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("计算器")
        self.root.geometry("400x500")
        self.root.resizable(False, False)
        
        # 设置窗口背景色
        self.root.configure(bg='#f0f0f0')
        
        # 计算器状态
        self.current = ""
        self.result = ""
        self.operation = ""
        self.reset_new_entry = True
        
        # 创建字体
        self.button_font = font.Font(family="Arial", size=14, weight="bold")
        self.display_font = font.Font(family="Arial", size=24, weight="bold")
        
        self.create_widgets()
    
    def create_widgets(self):
        # 显示屏
        self.display = tk.Entry(
            self.root, 
            font=self.display_font,
            bd=10, 
            insertwidth=2, 
            width=14, 
            borderwidth=4,
            justify='right',
            bg='white'
        )
        self.display.grid(row=0, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")
        
        # 按钮配置
        button_config = {
            'font': self.button_font,
            'width': 8,
            'height': 2,
            'bd': 2,
            'relief': 'raised',
            'cursor': 'hand2'
        }
        
        # 按钮颜色
        colors = {
            'numbers': '#e0e0e0',
            'operators': '#ff9500',
            'functions': '#a0a0a0',
            'equals': '#ff6b6b',
            'clear': '#ff6b6b'
        }
        
        # 创建按钮
        buttons = [
            ('C', 1, 0, colors['clear'], self.clear_all),
            ('⌫', 1, 1, colors['functions'], self.backspace),
            ('÷', 1, 2, colors['operators'], lambda: self.append_operator('/')),
            ('×', 1, 3, colors['operators'], lambda: self.append_operator('*')),
            
            ('7', 2, 0, colors['numbers'], lambda: self.append_number('7')),
            ('8', 2, 1, colors['numbers'], lambda: self.append_number('8')),
            ('9', 2, 2, colors['numbers'], lambda: self.append_number('9')),
            ('-', 2, 3, colors['operators'], lambda: self.append_operator('-')),
            
            ('4', 3, 0, colors['numbers'], lambda: self.append_number('4')),
            ('5', 3, 1, colors['numbers'], lambda: self.append_number('5')),
            ('6', 3, 2, colors['numbers'], lambda: self.append_number('6')),
            ('+', 3, 3, colors['operators'], lambda: self.append_operator('+')),
            
            ('1', 4, 0, colors['numbers'], lambda: self.append_number('1')),
            ('2', 4, 1, colors['numbers'], lambda: self.append_number('2')),
            ('3', 4, 2, colors['numbers'], lambda: self.append_number('3')),
            ('=', 4, 3, colors['equals'], self.calculate),
            
            ('0', 5, 0, colors['numbers'], lambda: self.append_number('0')),
            ('.', 5, 1, colors['numbers'], lambda: self.append_number('.')),
            ('±', 5, 2, colors['functions'], self.toggle_sign),
            ('=', 5, 3, colors['equals'], self.calculate)
        ]
        
        # 创建所有按钮
        for (text, row, col, color, command) in buttons:
            btn = tk.Button(
                self.root,
                text=text,
                bg=color,
                fg='white' if color in [colors['operators'], colors['equals'], colors['clear']] else 'black',
                command=command,
                **button_config
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            
            # 绑定键盘事件
            if text in '0123456789':
                self.root.bind(f'<Key-{text}>', lambda e, num=text: self.append_number(num))
            elif text == '.':
                self.root.bind('<period>', lambda e: self.append_number('.'))
            elif text == 'C':
                self.root.bind('<Escape>', lambda e: self.clear_all())
            elif text == '⌫':
                self.root.bind('<BackSpace>', lambda e: self.backspace())
            elif text == '+':
                self.root.bind('<plus>', lambda e: self.append_operator('+'))
            elif text == '-':
                self.root.bind('<minus>', lambda e: self.append_operator('-'))
            elif text == '×':
                self.root.bind('<asterisk>', lambda e: self.append_operator('*'))
            elif text == '÷':
                self.root.bind('<slash>', lambda e: self.append_operator('/'))
            elif text == '=':
                self.root.bind('<Return>', lambda e: self.calculate())
                self.root.bind('<equal>', lambda e: self.calculate())
        
        # 配置网格权重
        for i in range(4):
            self.root.grid_columnconfigure(i, weight=1)
        for i in range(6):
            self.root.grid_rowconfigure(i, weight=1)
    
    def update_display(self):
        self.display.delete(0, tk.END)
        self.display.insert(0, self.current if self.current else "0")
    
    def append_number(self, number):
        if self.reset_new_entry:
            self.current = ""
            self.reset_new_entry = False
        
        if number == '.' and '.' in self.current:
            return
        
        if self.current == "0" and number != '.':
            self.current = number
        else:
            self.current += number
        
        self.update_display()
    
    def append_operator(self, operator):
        if self.current and not self.reset_new_entry:
            self.calculate()
        
        self.operation = operator
        self.result = self.current
        self.reset_new_entry = True
        self.current = ""
        
        # 在显示中显示操作
        operator_symbols = {'*': '×', '/': '÷'}
        display_op = operator_symbols.get(operator, operator)
        self.display.delete(0, tk.END)
        self.display.insert(0, f"{self.result} {display_op}")
    
    def calculate(self):
        if not self.current or not self.operation or not self.result:
            return
        
        try:
            num1 = float(self.result)
            num2 = float(self.current)
            
            if self.operation == '+':
                result = num1 + num2
            elif self.operation == '-':
                result = num1 - num2
            elif self.operation == '*':
                result = num1 * num2
            elif self.operation == '/':
                if num2 == 0:
                    self.current = "错误：除零"
                    self.update_display()
                    self.reset_new_entry = True
                    return
                result = num1 / num2
            
            self.current = str(result)
            self.operation = ""
            self.result = ""
            self.reset_new_entry = True
            self.update_display()
            
        except ValueError:
            self.current = "错误"
            self.update_display()
            self.reset_new_entry = True
    
    def clear_all(self):
        self.current = ""
        self.result = ""
        self.operation = ""
        self.reset_new_entry = True
        self.update_display()
    
    def backspace(self):
        if self.current and not self.reset_new_entry:
            self.current = self.current[:-1]
            if not self.current:
                self.current = "0"
            self.update_display()
    
    def toggle_sign(self):
        if self.current and not self.reset_new_entry:
            if self.current.startswith('-'):
                self.current = self.current[1:]
            else:
                self.current = '-' + self.current
            self.update_display()

def main():
    root = tk.Tk()
    calculator = Calculator(root)
    root.mainloop()

if __name__ == "__main__":
    main()