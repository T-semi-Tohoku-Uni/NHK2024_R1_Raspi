from NHK2024_Raspi_Library import MainController, TwoStateButton, TwoStateButtonHandler, ThreeStateButton, ThreeStateButtonHandler
import json
import sys
from typing import Dict
from enum import Enum

class CANList(Enum):
    ARM_EXPANDER = 0x103
    HAND1 = 0x105
    HAND2 = 0X106
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

class R1MainController(MainController):
    def __init__(self, host_name, port):
        super().__init__(host_name=host_name, port=port)
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
                    print(f"Invalid key is included in the data: {e}")
                    continue
                
        except KeyboardInterrupt as e:
            self.log_system.write(f"R1Controller main stopped")
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
            action_send_1=lambda: self.write_can_bus(CANList.BALL_HAND.value, bytearray([1]))
        )
        
        # 発射
        self.btn_rb_state.handle_button(
            is_pressed=data.btn_rb,
            action_send_0=lambda: self.write_can_bus(CANList.SHOOT.value, bytearray([0])),
            action_send_1=lambda: self.write_can_bus(CANList.SHOOT.value, bytearray([1]))
        )
        
        # 速度制御
        self.write_can_bus(CANList.ROBOT_VEL.value, bytearray([data.v_x, data.v_y, data.omega]))
        
if __name__ == "__main__":
    host_name = "raspberrypi.local"
    port = 12345
    r2_main_controller = R1MainController(host_name=host_name, port=port)
    r2_main_controller.main()