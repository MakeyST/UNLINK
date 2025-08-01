import os
from app import create_one_time_link

FILES = {
    "0": "Makey_HWID_LifeTime.rar",
    "1": "Makey_HWID_1_use.rar"
}


def main():
    print("Выберите файл для генерации одноразовой ссылки:")
    print("0 - Makey_HWID_LifeTime.rar")
    print("1 - Makey_HWID_1_use.rar")

    choice = input("Введите 0 или 1: ").strip()

    if choice not in FILES:
        print("Неверный выбор.")
        return

    filename = FILES[choice]
    filepath = os.path.join('./uploads', filename)

    if not os.path.exists(filepath):
        print(f"Файл '{filename}' не найден в папке ./uploads")
        return

    link = create_one_time_link(filename)
    print("\n✅ Одноразовая ссылка создана:\n")
    print(link)


if __name__ == "__main__":
    main()
