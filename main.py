import multiprocessing
from src.ui.app import App

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()
