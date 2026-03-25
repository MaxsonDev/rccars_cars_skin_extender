import os
import re
import json
from struct import unpack, pack
from typing import Union
from io import BytesIO


def tiohReadByte(fb):
    data = fb.read(1)
    if data == b'' or len(data) != 1:
        return None
    return unpack("B", data)[0]


def tiohReadWord(fb):
    data = fb.read(2)
    if data == b'' or len(data) != 2:
        return None
    return unpack("H", data)[0]


def tiohReadDWord(fb):
    data = fb.read(4)
    if data == b'' or len(data) != 4:
        return None
    return unpack("I", data)[0]


def tiohReadString(fb):
    _str = b''
    while True:
        c = fb.read(1)
        if c == b'\0' or c == b'':
            return _str.decode('cp437')
        else:
            _str += c


def tiohWriteByte(fb, data):
    fb.write(pack("B", data))


def tiohWriteWord(fb, data):
    fb.write(pack("H", data))


def tiohWriteDWord(fb, data):
    fb.write(pack("I", data))


def tiohWriteString(fb, data: str):
    txt_byte = data.encode("ascii")
    fb.write(txt_byte)
    fb.write(b"\0")


class RCCarsSkinExtender:
    def __init__(self):
        self.skin_list: list = []
        # лучший путь - кинуть питон файл в корень игры. а лучше использовать exe из репозитория
        # self.current_path = "C:\\path\\to\\game\\folder"
        self.current_path = os.getcwd()
        self.sb_path = os.path.join(self.current_path, "RCCars.sb")
        self.exe_path = os.path.join(self.current_path, "RCCars.exe")
        config_path = os.path.join(self.current_path, "config.json")
        with open(config_path, "r") as f:
            self.config = json.load(f)

        # SB
        self.fb_sb: Union[BytesIO, None] = None
        self.sb_file_size: int = 0
        self.DESC_ptr_end_address: int = 0x304

        # EXE
        self.fb_exe: Union[BytesIO, None] = None
        self.cmp_tex_ptr: int = 0x9FCA8
        self.rtn_tex_size: int = 0x9FD67
        self.cmp_skin_ico_ptr: int = 0xAD05F
        self.cmp_tex_mplr_ptr: int = 0x9EF50
        self.csi_max_tex_ptr: int = 0xA26C5

    def run(self):
        self.check_skin_total_size()
        if self.config["patch_sb"] is True:
            self.patch_sb_file()
        if self.config["patch_exe"] is True:
            self.patch_exe_file()

    def check_skin_total_size(self):
        total_size = self.config["skin_total_size"]
        if total_size < 4 or total_size > 255:
            raise Exception('Неверное значение ключа "skin_total_size" в конфиге. Количество скинов может быть задано числами от 4 до 255.')

    def patch_sb_file(self):
        try:
            self.fb_sb = open(self.sb_path, "r+b")
        except FileNotFoundError:
            raise FileNotFoundError("Неправильный путь к RCCars.sb файлу или файл отсутствует.")
        try:
            self.fb_sb.seek(0, 2)
            self.sb_file_size = self.fb_sb.tell()
            self.fb_sb.seek(0, 0)
            self._check_sb_file_headers()
            self._add_new_car_skin()
        except Exception as ex:
            raise ex
        finally:
            self.fb_sb.close()

    def _check_sb_file_headers(self):
        magic = tiohReadWord(self.fb_sb)
        if magic == 0x3801:
            tiohReadDWord(self.fb_sb)
            version = tiohReadDWord(self.fb_sb)
            if version == 0x60000:
                chunk = tiohReadWord(self.fb_sb)
                if chunk == 0x4802:
                    tiohReadDWord(self.fb_sb)
                    string = tiohReadString(self.fb_sb)
                    if string == "CREAT Studio Scene Project 6.0":
                        self.fb_sb.seek(0x302)
                        chunk = tiohReadWord(self.fb_sb)
                        address = tiohReadDWord(self.fb_sb)
                        desc_mod = tiohReadDWord(self.fb_sb)
                        if chunk == 0x9200:
                            if address == self.sb_file_size:
                                if desc_mod == 0x44455343:
                                    return
        raise Exception("Заголовки SB файла повреждены или это не SB файл.")

    def _add_new_car_skin(self):
        # 1. Получим список текстур в текстовом представлении
        # Не будем добавлять текстуры, которые уже есть в файле
        self.fb_sb.seek(0)
        text = self.fb_sb.read().decode("ascii", errors="ignore")
        # 2. Поcчитаем скины по шаблону
        skin_list = re.findall(r"car_[ab]skin\d{1,4}", text)
        # 3. Перейдем на конец файла
        self.fb_sb.seek(self.sb_file_size)
        # 4. Создадим новые GLTX
        for skin_i in range(self.config["skin_total_size"]):
            skin_i += 1
            # пропускаем стандартные 4 скина
            if skin_i <= 4:
                continue
            for car_id_i in range(3):
                car_id_i += 1
                name_a = f"car_askin{car_id_i}{skin_i}"
                name_b = f"car_bskin{car_id_i}{skin_i}"
                if car_id_i == 1:
                    if name_a not in skin_list:
                        self._write_gltx_in_sb(name_a)
                else:
                    if name_a not in skin_list:
                        self._write_gltx_in_sb(name_a)
                    if name_b not in skin_list:
                        self._write_gltx_in_sb(name_b)
        # 5. Поменяем адрес на конец DESC
        self.fb_sb.seek(0, 2)
        end_desc_adr = self.fb_sb.tell()
        self.fb_sb.seek(self.DESC_ptr_end_address)
        tiohWriteDWord(self.fb_sb, end_desc_adr)

    def _write_gltx_in_sb(self, skin_name):
        # 1. init mod
        mod_start_adr = self.fb_sb.tell()
        # write 0x9200
        tiohWriteWord(self.fb_sb, 0x9200)
        # write empty 0
        tiohWriteDWord(self.fb_sb, 0)
        # write mod GLTX
        tiohWriteDWord(self.fb_sb, 0x474C5458)

        # chunk_start_adr = 0
        # chunk_end_adr = 0

        # 2. Name init
        chunk_start_adr = self.fb_sb.tell()
        tiohWriteWord(self.fb_sb, 0x4003)
        # write empty adr 0
        tiohWriteDWord(self.fb_sb, 0)
        # write data
        tiohWriteString(self.fb_sb, skin_name)
        chunk_end_adr = self.fb_sb.tell()
        self.fb_sb.seek(chunk_start_adr + 2)
        # rewrite adr
        tiohWriteDWord(self.fb_sb, chunk_end_adr)
        self.fb_sb.seek(chunk_end_adr)

        # 3. Params
        chunk_start_adr = chunk_end_adr
        # размер данных уже известен
        chunk_end_adr = chunk_start_adr + 0x1E
        tiohWriteWord(self.fb_sb, 0x3408)
        # write adr
        tiohWriteDWord(self.fb_sb, chunk_end_adr)
        # write arg_count 5 and args value
        tiohWriteDWord(self.fb_sb, 5)
        [tiohWriteDWord(self.fb_sb, 0) for _ in range(2)]
        tiohWriteDWord(self.fb_sb, 0x20000010)
        [tiohWriteDWord(self.fb_sb, 0) for _ in range(2)]

        # 4. Chunk 2431h
        chunk_start_adr = chunk_end_adr
        chunk_end_adr = chunk_start_adr + 0x12
        tiohWriteWord(self.fb_sb, 0x3408)
        # write adr
        tiohWriteDWord(self.fb_sb, chunk_end_adr)
        # write arg_count 2 and args
        tiohWriteDWord(self.fb_sb, 2)
        [tiohWriteDWord(self.fb_sb, 0) for _ in range(2)]

        # 5. Rewrite MOD addr
        self.fb_sb.seek(mod_start_adr + 2)
        # write adr
        tiohWriteDWord(self.fb_sb, chunk_end_adr)
        self.fb_sb.seek(chunk_end_adr)

    def patch_exe_file(self):
        try:
            self.fb_exe = open(self.exe_path, "r+b")
        except FileNotFoundError:
            raise Exception("Неправильный путь к RCCars.exe файлу или файл отсутствует.")
        try:
            self._check_exe_file_headers()
            self._patch_exe()
        except Exception as ex:
            raise ex
        finally:
            self.fb_exe.close()

    def _check_exe_file_headers(self):
        magic = self.fb_exe.read(2)
        if magic == b'MZ':
            self.fb_exe.seek(0x3C)
            header_ptr = tiohReadDWord(self.fb_exe)
            self.fb_exe.seek(header_ptr)
            more_magic = self.fb_exe.read(4)
            if more_magic == b'PE\0\0':
                return
        raise Exception("Заголовки EXE файла повреждены или это не EXE файл.")

    def _patch_exe(self):
        # меняем значение в проверке максимального значения ID скина
        self.fb_exe.seek(self.cmp_tex_ptr)
        tiohWriteByte(self.fb_exe, self.config["skin_total_size"])
        # меняем значение в возврате максимального значения
        self.fb_exe.seek(self.rtn_tex_size)
        tiohWriteDWord(self.fb_exe, self.config["skin_total_size"])
        # меняем значение в проверке иконок
        self.fb_exe.seek(self.cmp_skin_ico_ptr)
        tiohWriteByte(self.fb_exe, self.config["skin_total_size"])
        # меняем значение в проверке максимального значения ID в мультиплеере
        self.fb_exe.seek(self.cmp_tex_mplr_ptr)
        tiohWriteByte(self.fb_exe, self.config["skin_total_size"])
        # увеличим лимит на текстуры
        csi_max_tex_size = 500
        new_csi_max_tex_size = csi_max_tex_size + (self.config["skin_total_size"] - 4) * 5
        self.fb_exe.seek(self.csi_max_tex_ptr)
        tiohWriteDWord(self.fb_exe, new_csi_max_tex_size)


if __name__ == "__main__":
    try:
        extender = RCCarsSkinExtender()
        extender.run()
    except Exception as ex:
        raise ex
