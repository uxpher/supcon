import time
import dexhandpy.fdexhand as fdh

class DexhandDemo:
    def __init__(self):
        self.dh = fdh.DexHand()
        self.result = fdh.Ret

    def init(self):
        ret = self.dh.init()
        if (ret == self.result.SUCCESS):
            print("init successfully")
        else:
            print("init failed")
            exit(0)

    def reboot(self):
        ret = self.dh.reboot()
        if ret == self.result.SUCCESS:
            print("reboot successfully")
        else:
            print("reboot failed")

    def device_info(self):
        ip_list = self.dh.get_ip_list()
        for ip in ip_list:
            name = self.dh.get_name(ip)
            type = self.dh.get_type(ip)
            dri_ver = self.dh.get_driver_ver(ip)
            hw_ver = self.dh.get_hardware_ver(ip)
            print(f"{ip}, name:{name}, type:{type}, driver_ver:{dri_ver}, hardware_ver:{hw_ver}")

    def get_pos(self):
        ip_list = self.dh.get_ip_list()
        for ip in ip_list:
            pos = self.dh.get_pos(ip)
            print(f"{ip}, pos: {[f'{x:.2f}' for x in pos]}")

    def set_pos(self):
        ip_list = self.dh.get_ip_list()
        for ip in ip_list:
            if self.dh.get_name(ip) == "fdhv2":
                self.dh.set_pos(ip, [0] * 12)
            else:
                self.dh.set_pos(ip, [1] * 6)

    def get_ts_matrix(self):
        ip_list = self.dh.get_ip_list()
        for ip in ip_list:
            if self.dh.get_name(ip) == "fdhv2":
                print(f"{ip}, matrix: ")
                ts_matrix = self.dh.get_ts_matrix(ip)
                for row in ts_matrix:
                    print(f"{row}")

    def get_hand_config(self):
        ip_list = self.dh.get_ip_list()
        for ip in ip_list:
            config = self.dh.get_hand_config(ip)
            print(f"result {config.result}, ip: {config.ip}, gateway: {config.gateway}, sn: {config.sn}, mac: {config.mac}")

    def get_pvc(self):
        ip_list = self.dh.get_ip_list()
        for ip in ip_list:
            pvc = self.dh.get_pvc(ip)
            if pvc:
                print(f"{ip}, p: {[f'{x:.2f}' for x in pvc[0]]}")
                print(f"{ip}, v: {[f'{x:.2f}' for x in pvc[1]]}")
                print(f"{ip}, c: {[f'{x:.2f}' for x in pvc[2]]}")

    def set_pvc(self):
        ip_list = self.dh.get_ip_list()
        for ip in ip_list:
            pvc = []
            if (self.dh.get_name(ip) == "fdhv2"):
                pvc = [[0] * 12, [1] * 12, [0] * 12]
            else:
                pvc = [[1] * 6, [2] * 6, [0] * 6]

            ret = self.dh.set_pvc(ip, pvc)
            if (ret == self.result.SUCCESS):
                print("set_pvc successfully")
            else:
                print("set_pvc failed")


def main():
    Demo = DexhandDemo()
    Demo.init()
    Demo.device_info()
    Demo.set_pos()
    Demo.get_pos()
    Demo.get_ts_matrix()
    Demo.get_hand_config()
    Demo.get_pvc()
    Demo.set_pvc()

    time.sleep(1)
    Demo.reboot()

if __name__ == "__main__":
    main()

