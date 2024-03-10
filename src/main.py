from NHK2024_Raspi_Library import MainController, TwoStateButton, TwoStateButtonHandler, ThreeStateButton, ThreeStateButtonHandler
import json
import sys
from typing import Dict, Callable
from enum import Enum
import can
import time

class CANList(Enum):
    ARM_EXPANDER = 0x103
    HAND1 = 0x105
    HAND2 = 0X106
    ARM_STATE = 0x107
    ARM_ELEVATOR = 0x104
    ARM1 = 0x108
    SHOOT = 0x101
    BALL_HAND = 0x102
    ROBOT_VEL = 0x10B

class ClientController:
    def __init__(self, data: Dict):
        try:
            self.v_x = data["v_x"]
            self.v_y = data["v_y"]
            self.omega = data["omega"]
            self.btn_a = data["btn_a"]
            self.btn_b = data["btn_b"]
            self.btn_x = data["btn_x"]
            self.btn_y = data["btn_y"]
            self.btn_lb = data["btn_lb"]
            self.btn_rb = data["btn_rb"]
            self.start_btn = data["start_btn"]
        except KeyError as e:
            raise KeyError("Invalid key is included in the data: {e}")

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
        print(f"Received: {msg.__str__()}")

class R1MainController(MainController):
    def __init__(self, host_name, port):
        super().__init__(host_name=host_name, port=port)
        
        # init can lister
        lister = R1CANLister()
        lister.init_write_fnc(self.log_system.write, self.log_system.update_received_can_log, self.log_system.update_send_can_log, self.log_system.update_error_log)
        lister.init_write_can_bus_func(self.write_can_bus)
        self.init_can_notifier(lister=lister)
        
        # init button state
        self.btn_a_state = TwoStateButtonHandler(state=TwoStateButton.WAIT_1)
        self.btn_b_state = TwoStateButtonHandler(state=TwoStateButton.WAIT_1)
        self.btn_x_state = ThreeStateButtonHandler(state=ThreeStateButton.WAIT_0)
        self.btn_y_state = TwoStateButtonHandler(state=TwoStateButton.WAIT_1)
        self.btn_lb_state = TwoStateButtonHandler(state=TwoStateButton.WAIT_1)
        self.btn_rb_state = TwoStateButtonHandler(state=TwoStateButton.WAIT_1)
        
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
            self.log_system.write(f"R1Controller main stopped")
            self.log_system.update_error_log(f"R1Controller main stopped")
            print(f"R1Controller main stopped")
    
    def parse_to_can_message(self, data: ClientController):
        # ボタンA関連(HAND1)
        self.btn_a_state.handle_button(
            is_pressed=data.btn_a,
            action_send_0=lambda: self.write_can_bus(CANList.HAND1.value, bytearray([0])),
            action_send_1=lambda: self.write_can_bus(CANList.HAND1.value, bytearray([1]))
        )
        
        # ボタンB関連(HAND2)
        self.btn_b_state.handle_button(
            is_pressed=data.btn_b,
            action_send_0=lambda: self.write_can_bus(CANList.HAND2.value, bytearray([0])),
            action_send_1=lambda: self.write_can_bus(CANList.HAND2.value, bytearray([1]))
        )
        
        # ボタンX関連(ARMの位置制御)
        self.btn_x_state.handle_button(
            is_pressed=data.btn_x,
            action_send_0=lambda: self.write_can_bus(CANList.ARM1.value, bytearray([0])),
            action_send_1=lambda: self.write_can_bus(CANList.ARM1.value, bytearray([1])),
            action_send_2=lambda: self.write_can_bus(CANList.ARM1.value, bytearray([2]))
        )
        
        # ボタンY関連(ARM_EXPANDER)
        self.btn_y_state.handle_button(
            is_pressed=data.btn_y,
            action_send_0=lambda: self.write_can_bus(CANList.ARM_EXPANDER.value, bytearray([0])),
            action_send_1=lambda: self.write_can_bus(CANList.ARM_EXPANDER.value, bytearray([1]))
        )
        
        # ボールの装填
        self.btn_lb_state.handle_button(
            is_pressed=data.btn_lb,
            action_send_0=lambda: self.write_can_bus(CANList.BALL_HAND.value, bytearray([0])),
            action_send_1=lambda: self.write_can_bus(CANList.ARM_STATE.value, bytearray([]))
        )
        
        # 発射
        self.btn_rb_state.handle_button(
            is_pressed=data.btn_rb,
            action_send_0=lambda: self.write_can_bus(CANList.SHOOT.value, bytearray([0])),
            action_send_1=lambda: self.write_can_bus(CANList.SHOOT.value, bytearray([1]))
        )
        
        # 速度制御
        self.write_can_bus(CANList.ROBOT_VEL.value, bytearray([data.v_x, data.v_y, data.omega]))
        
    def test(self):
        while True:
            self.write_can_bus(CANList.ARM_STATE.value, bytearray([0]))
            # self.write_can_bus(0x001, bytearray([1]))
            time.sleep(1)
        # for i in range(100):
        #     self.write_can_bus(i, bytearray([i]))
    
if __name__ == "__main__":
    host_name = "raspberrypi.local"
    port = 12345
    r2_main_controller = R1MainController(host_name=host_name, port=port)
    # r2_main_controller.main()
    r2_main_controller.test()