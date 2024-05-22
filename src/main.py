from NHK2024_Raspi_Library import MainController, TwoStateButton, TwoStateButtonHandler, ThreeStateButton, ThreeStateButtonHandler, OneStateButton, OneStateButtonHandler
import json
import sys
from typing import Dict, Callable, Optional
from enum import Enum
import can
import time
from area import SeedlingHandState, AreaState, SeedlingHandPosition, Area
from can_list import CANList
import multiprocessing

class CANList(Enum):
    # Seedling
    SEEDLING_ARM_SET = 0x109
    SEEDLING_ARM_OPEN = 0x151
    SEEDLING_ARM_SEEDLING_GET = 0x152
    SEEDLING_ARM_DOWM = 0x153
    SEEDLING_HAND_POSITION = 0x108
    SEEDLING_ARM_ELEVATOR = 0x104
    SEEDLING_INSIDE_HAND_OPEN = 0x105
    SEEDLING_OUTSIDE_HAND_OPEN = 0x106
    
    # Ball
    BALL_ARM_UNEXPAND = 0x103 # アーム収納（地面につける）
    BALL_BALL_HAND_OPEN = 0x102 # ボール回収用のアームを開く
    BALL_SHOOT = 0x101
    BALL_MOTOR_ON = 0x10A
    
    ARM_EXPANDER = 0x103
    HAND1 = 0x105
    HAND2 = 0X106
    ARM_STATE = 0x107
    ARM1 = 0x108
    SHOOT = 0x101
    BALL_HAND = 0x102
    ROBOT_VEL = 0x10B
    
    # ラズパイ => マイコン
    CHECK_INJECTION_MECHANISM = 0x300
    CHECK_SEEDLING_MECHANISM = 0x301
    CHECK_IS_ACTIVED = 0x500
    
    # マイコン => ラズパイ
    RESPONSE_INJECTION_MECHANISM = 0x400
    RESPONSE_SEEDLING_MECHANISM = 0x401

class ClientController:
    def __init__(self, data: Dict):
        try:
            self.btn_a = data["btn_a"]
            self.btn_b = data["btn_b"]
            self.btn_x = data["btn_x"]
            self.btn_y = data["btn_y"]
            # self.btn_lb = data["btn_lb"]
            self.btn_rb = data["btn_rb"]
            self.seedling_hand_pos = SeedlingHandPosition(data["seedling_hand_pos"])
            self.area_state = Area(data["area_state"])
           # self.start_btn = data["start_btn"]
        except KeyError as e:
            raise KeyError(f"Invalid key is included in the data: {e}")

class WheelDataFromClient:
    def __init__(self, data: Dict):
        try:
            self.v_x = data["v_x"]
            self.v_y = data["v_y"]
            self.omega = data["omega"]
        except KeyError as e:
            raise KeyError(f"Invalid key is included in the data: {e}")

class R1CANLister(can.Listener):
    def __init__(self):
        super().__init__()
        self.write = None
        self.write_with_can_id = None
    
    def init_write_fnc(self, write: Callable[[str], None], update_received_can_log: Callable[[can.Message], None], update_send_can_log: Callable[[can.Message], None], update_error_log: Callable[[str], None]):
        self.write = write
        self.update_received_can_log = update_received_can_log
        self.update_send_can_log = update_send_can_log
        self.update_error_log = update_error_log
        
    def init_write_can_bus_func(self, write_can_bus: Callable[[int, bytearray], None]):
        self.write_can_bus = write_can_bus
        
    def on_message_received(self, msg):
        can_id: int = int(msg.arbitration_id)
        data: str = msg.data.hex()
        is_error: bool = msg.is_error_frame

        if can_id == CANList.ARM_STATE.value and data == bytearray([1]): # ARM is up state
            self.write_can_bus(CANList.BALL_HAND.value, bytearray([1]))
        
        if is_error is True:
            self.update_error_log(msg.__str__())
            print(f"Get Error Frame: {msg.__str__()}")
        
        # write log file
        if self.write is None or self.update_send_can_log is None or self.update_received_can_log is None:
            print("write function is not initialized")
            return
        
        self.write(f"Received: {msg.__str__()}")
        self.update_received_can_log(msg)
        # print(f"Received: {msg.__str__()}")

class R1MainController(MainController):
    def __init__(self, host_name, port, port_for_wheel_controle):
        super().__init__(host_name=host_name, port=port, port_for_wheel_controle=port_for_wheel_controle)
        
        # init can lister
        lister = R1CANLister()
        lister.init_write_fnc(self.log_system.write, self.log_system.update_received_can_log, self.log_system.update_send_can_log, self.log_system.update_error_log)
        lister.init_write_can_bus_func(self.write_can_bus)
        self.init_can_notifier(lister=lister)
        
        # init button state
        self.btn_a_state = TwoStateButtonHandler(state=TwoStateButton.WAIT_1)
        # self.btn_a_state = OneStateButtonHandler(state=OneStateButton.WAIT)
        self.btn_b_state = TwoStateButtonHandler(state=TwoStateButton.WAIT_1)
        self.btn_x_state = TwoStateButtonHandler(state=TwoStateButton.WAIT_1)
        # self.btn_y_state = OneStateButtonHandler(state=OneStateButton.WAIT)
        self.btn_y_state = TwoStateButtonHandler(state=TwoStateButton.WAIT_1)
        # self.btn_lb_state = TwoStateButtonHandler(state=TwoStateButton.WAIT_1)
        
        self.btn_rb_state = OneStateButtonHandler()
        # self.btn_rb_state = TwoStateButtonHandler(state=TwoStateButton.WAIT_1)
        
        # init hand state
        self.seedling_hand_state = SeedlingHandState()
        
        # start manageWheelControl at sub thread
        self.process_for_wheel = multiprocessing.Process(target=self.manageWheelControl)
        self.process_for_wheel.start()
        self.log_system.write("Start manageWheelControl")
        print("Start manageWheelControl")
       
        # ラズパイとの生存確認用メッセージ
        self.process_for_is_active = multiprocessing.Process(target=self.sendIsActiveMessage)
        self.process_for_is_active.start()
        
        # init area state
        self.area_state = AreaState(
            initialize_seedling_state=self.initialize_seedling_state, 
            initialize_ball_state=self.initialize_ball_state,
            initialize_start_state=self.initialize_start_state
        )

        print("Initialize Controller")
        
    def main(self):
        self.log_system.write(f"Start R1Controller main")
        print(f"Start R1Controller main")

        
        try:
            while True:
                raw_ctr_data = json.loads(self.read_udp())
                
                try:
                    ctr_data = ClientController(raw_ctr_data)
                    self.parse_to_can_message(ctr_data)
                except KeyError as e:
                    self.log_system.write(f"Invalid key is included in the data: {e}")
                    self.log_system.update_error_log(f"Invalid key is included in the data: {e}")
                    print(f"Invalid key is included in the data: {e}")
                    continue
                
        except KeyboardInterrupt as e:
            self.process_for_wheel.terminate()
            self.process_for_wheel.join()
            self.log_system.write("manageWheelControl stopped")
            self.log_system.update_error_log("manageWheelControl stopped")
            print("manageWheelControl stopped")
            self.process_for_is_active.terminate()
            self.process_for_is_active.join()
            self.log_system.write("isCheckActived stop")
            self.log_system.update_error_log("isCheckActived stop")
            print("isCheckActived stop")
            self.log_system.write(f"R1Controller main stopped")
            self.log_system.update_error_log(f"R1Controller main stopped")
            print(f"R1Controller main stopped")
    
    # ロボットの足回りの制御をする
    # mainスレッドとは別のスレッドで非同期に実行する
    def manageWheelControl(self):
        self.log_system.write("Start Wheel Control")
        print("Start Wheel Control")

        while True:
            raw_wheel_data = json.loads(self.read_udp_for_wheel_controle())
            try:
                wheel_data = WheelDataFromClient(raw_wheel_data)
                self.write_can_bus(CANList.ROBOT_VEL.value, bytearray([wheel_data.v_x, wheel_data.v_y, wheel_data.omega]))
            except KeyError as e:
                self.log_system.write(f"Invalid key is included in the data: {e}")
                self.log_system.update_error_log(f"Invalid key is included in the data: {e}")
                print(f"Invalid key is included in the data: {e}")
                continue
            except:
                self.log_system.write("Unknown Error")
                self.log_system.update_error_log("Unknown Error")
                print("Unknown Error")
                continue
    
    def sendIsActiveMessage(self):
        self.log_system.write("Start sendIsActiveMessage")
        print("Start sendIsActiveMessage")

        while True:
            self.write_can_bus(CANList.CHECK_IS_ACTIVED.value, bytearray([]))
            time.sleep(0.1)

    def parse_to_can_message(self, data: ClientController):
        
        # area_stateの状態変更はここで
        self.area_state.set_state(data.area_state)
        
        print(self.area_state.is_start())
        
        if self.area_state.is_seedling():
            # 苗ハンドの位置設定
            self.seedling_hand_state.update_state(data.seedling_hand_pos, self.write_can_bus)
            
            (seedling_hand_action_send_0, seedling_hand_action_send_1) = \
                self.seedling_hand_state.set_btn_y_handler(self.write_can_bus)
                
            # 苗ハンドの開閉（ボタンY）
            self.btn_y_state.handle_button(
                is_pressed=data.btn_y,
                action_send_0=seedling_hand_action_send_0,
                action_send_1=seedling_hand_action_send_1
            )
            
            # 苗アームの上下
            self.btn_a_state.handle_button(
                is_pressed=data.btn_a,
                action_send_0=lambda: self.write_can_bus(CANList.SEEDLING_ARM_ELEVATOR.value, bytearray([0])),
                action_send_1=lambda: self.write_can_bus(CANList.SEEDLING_ARM_ELEVATOR.value, bytearray([1]))
            )
        
        if self.area_state.is_ball():
            # ボール回収用のアームの開閉（ボタンB）
            self.btn_b_state.handle_button(
                is_pressed=data.btn_b,
                action_send_0=lambda: self.write_can_bus(CANList.BALL_BALL_HAND_OPEN.value, bytearray([0])),
                action_send_1=lambda: self.write_can_bus(CANList.BALL_BALL_HAND_OPEN.value, bytearray([1]))
            )
            
            # ボール回収用のアームを地面につける（ボタンX）
            self.btn_x_state.handle_button(
                is_pressed=data.btn_x,
                action_send_0=lambda: self.write_can_bus(CANList.BALL_ARM_UNEXPAND.value, bytearray([0])),
                action_send_1=lambda: self.write_can_bus(CANList.BALL_ARM_UNEXPAND.value, bytearray([1]))
            )
            
            # ボールの発射 (ボタンrb)
            self.btn_rb_state.handle_button(
                is_pressed=data.btn_rb,
                action_send=self.shoot_ball
            )
            
        # mainのUDPバッファを空にする
        self.clear_udp_socket(self.sock)
    
    def initialize_start_state(self):
        print("initialize start state")
        
        # 射出部分の掴むところを格納
        self.write_can_bus(CANList.BALL_ARM_UNEXPAND.value, bytearray([1]))
        self.write_can_bus(CANList.BALL_HAND.value, bytearray([0]))
        
        time.sleep(0.5)
        
        # 苗アームをup
        self.write_can_bus(CANList.SEEDLING_ARM_ELEVATOR.value, bytearray([0]))
        self.btn_a_state.transision_next_state(1)
        
        time.sleep(1)
        
        # 安全のため1秒停止, TODO: どれぐらいの秒数が必要なのか確認
        
        # 射出部分をdown
        self.write_can_bus(CANList.SHOOT.value, bytearray([1]))
        
        # アームの制御を止める
        self.write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.RESET.value]))
        
        # mainのUDPバッファを空にする
        self.clear_udp_socket(self.sock)
        
        pass
    
    def initialize_seedling_state(self):
        print("initialize seddling state")
        # 射出部分の掴むところを格納
        self.write_can_bus(CANList.BALL_ARM_UNEXPAND.value, bytearray([1]))
        self.write_can_bus(CANList.BALL_HAND.value, bytearray([0]))
        
        # 安全のため1秒停止, TODO: どれぐらいの秒数が必要なのか確認
        time.sleep(1)
        
        # 射出部分を上に上げる
        self.write_can_bus(CANList.SHOOT.value, bytearray([0]))
        
        # 完了メッセージが届くまで待つ
        # self.write_can_bus(CANList.CHECK_INJECTION_MECHANISM.value, bytearray([]))
        # if self.wait_can_message(CANList.RESPONSE_INJECTION_MECHANISM.value, timeout=5) is None:
        #     self.log_system.update_error_log("Error: Cannot recive RESPONSE_INJECTION_MECHANISM")
        #     self.log_system.write("Error: Cannot recive RESPONSE_INJECTION_MECHANISM")
        #     print("Error: Cannot recive RESPONSE_INJECTION_MECHANISM")
        #     return
        
        time.sleep(2)
        
        # 完了後に次の動作を行う
        # TODO: もしかしたら逆かもしれないので、チェックする
        # アームを下ろす
        self.write_can_bus(CANList.SEEDLING_ARM_ELEVATOR.value, bytearray([1]))
        self.btn_a_state.transision_next_state(1)
        # ハンドの腕を下ろす
        self.write_can_bus(CANList.SEEDLING_ARM_SET.value, bytearray([1]))
        # ハンドを開く
        self.write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.PICKUP.value]))
        self.write_can_bus(CANList.SEEDLING_INSIDE_HAND_OPEN.value, bytearray([1]))
        self.write_can_bus(CANList.SEEDLING_OUTSIDE_HAND_OPEN.value, bytearray([1]))
        self.seedling_hand_state.reset_state(SeedlingHandPosition.PICKUP.value)
        self.btn_a_state.transision_next_state(1)
        self.btn_y_state.transision_next_state(1)
        
        # mainのUDPバッファを空にする
        self.clear_udp_socket(self.sock)

        return
    
    # TODO: test
    def initialize_ball_state(self):
        
        print("Initialize ball state")
        self.write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.PUTINSIDE.value]))
        time.sleep(1)
        self.write_can_bus(CANList.SEEDLING_ARM_ELEVATOR.value, bytearray([0]))
        self.write_can_bus(CANList.SEEDLING_ARM_SET.value, bytearray([0]))
        self.write_can_bus(CANList.SEEDLING_INSIDE_HAND_OPEN.value, bytearray([0]))
        self.write_can_bus(CANList.SEEDLING_OUTSIDE_HAND_OPEN.value, bytearray([0]))
        
        self.btn_a_state.transision_next_state(0)
        self.btn_y_state.transision_next_state(0)
        self.seedling_hand_state.reset_state(SeedlingHandPosition.PUTINSIDE.value)
        
        # self.write_can_bus(CANList.CHECK_SEEDLING_MECHANISM.value, bytearray([]))
        # if self.wait_can_message(CANList.RESPONSE_SEEDLING_MECHANISM.value, timeout=5) is None:
        #     self.log_system.update_error_log("Error: Cannot recive RESPONSE_SEEDLING_MECHANISM")
        #     self.log_system.write("Error: Cannot recive RESPONSE_SEEDLING_MECHANISM")
        #     print("Error: Cannot recive RESPONSE_SEEDLING_MECHANISM")
        #     return
        
        time.sleep(2)
        
        self.write_can_bus(CANList.SHOOT.value, bytearray([1]))
        
        # ボタンの状態を更新する
        self.btn_x_state.transision_next_state(1)
        self.btn_b_state.transision_next_state(0)
        
        # mainのUDPバッファを空にする
        self.clear_udp_socket(self.sock)
        
        return
    
    def shoot_ball(self):
        # モータ回す
        self.write_can_bus(CANList.BALL_MOTOR_ON.value, bytearray([1]))
        # 1秒停止
        time.sleep(2)
        # ボール発射
        # マイコン側で、ボールのアームを格納するようにする
        self.write_can_bus(CANList.BALL_SHOOT.value, bytearray([0]))
        # 一秒停止
        time.sleep(2)
        # 射出機構を元に戻す
        self.write_can_bus(CANList.BALL_MOTOR_ON.value, bytearray([0]))
        self.write_can_bus(CANList.BALL_SHOOT.value, bytearray([1]))
        
        # ボタンの状態を更新する
        self.btn_x_state.transision_next_state(1)
        self.btn_b_state.transision_next_state(0)
        
        # mainのUDPバッファを空にする
        self.clear_udp_socket(self.sock)
    
    def wait_can_message(self, can_id: int, timeout=0.5) -> Optional[can.Message]:
        filters = [{
            "can_id": can_id,
            "can_mask": 0x7FF
        }]
        
        with can.interface.Bus(channel='can0', bustype='socketcan', bitrate=1000000, fd=True, data_bitrate=2000000) as bus:
            bus.set_filters(filters=filters)
            msg = bus.recv(timeout=timeout)
            
        return msg
    
    def test(self):
        # self.btn_a_state.handle_button(
        #     is_pressed=1,
        #     action_send = self.get_seedling_with_arm
        # )
        # self.write_can_bus(CANList.ROBOT_VEL.value, bytearray([160, 127, 127]))
        # self.write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.RESET.value]))
        self.write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.RESET.value]))
        time.sleep(1)
        self.write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.PUTOUTSIDE.value]))
        time.sleep(2)
        self.write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.RESET.value]))
        time.sleep(1)
        self.write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.PUTINSIDE.value]))
    
if __name__ == "__main__":
    host_name = "tsemiR1.local"
    port = 12345
    port_for_wheel_controle = 12346
    r2_main_controller = R1MainController(host_name=host_name, port=port, port_for_wheel_controle=port_for_wheel_controle)
    r2_main_controller.main()
    # r2_main_controller.test()
   # time.sleep(5)
    #r2_main_controller.initialize_ball_state()
    #time.sleep(5)
    #r2_main_controller.initialize_seedling_state()
    # dict = {
    #     "v_x" : 100,
    #     "v_y" : 100,
    #     "omega": 100,
    #     "btn_a" : 1,
    #     "btn_b" : 0,
    #     "btn_y" : 1,
    #     "btn_x" : 1,
    #     "btn_rb" : 1,
    #     "seedling_hand_pos": 0,
    #     "area_state": 1
    # }
    # r2_main_controller.parse_to_can_message(ClientController(dict))
    # r2_main_controller.parse_to_can_message(dict)
    
