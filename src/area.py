from enum import Enum
from typing import Callable, Tuple
from can_list import CANList
import time

class Area(Enum):
    SEEDLING = 0
    BALL = 1
    START = 2
    
class AreaState:
    def __init__(
            self, 
            initialize_seedling_state: Callable[[], None], 
            initialize_ball_state: Callable[[], None], 
            initialize_start_state: Callable[[], None],
            state=Area.START
        ) -> None:
        self.state = state
        self.initialize_seedling_state = initialize_seedling_state
        self.initialize_ball_state = initialize_ball_state
        self.initialize_start_state = initialize_start_state
        self.set_state(state=state)
    def set_state(self, state: Area):
        # state not change, pass
        if self.state == state:
            return
        
        if state == Area.START:
            self.state = state
            self.initialize_start_state()
        
        # new state is seedling
        if state == Area.SEEDLING:
            # Update state
            self.state = state
            
            # TODO: initialize robot state
            self.initialize_seedling_state()
        
        # new state is ball
        if state == Area.BALL:
            # Update state
            self.state = state
            
            # TODO: initialize robot state
            self.initialize_ball_state()
    
    def get_state(self) -> Area:
        return self.state
    
    def is_start(self) -> Area:
        return self.state == Area.START
    
    def is_seedling(self) -> bool:
        return self.state == Area.SEEDLING

    def is_ball(self) -> bool:
        return self.state == Area.BALL
    
class SeedlingHandPosition(Enum):
    PICKUP = 0
    PUTOUTSIDE = 1
    PUTINSIDE = 2
    RESET = 3
    
class SeedlingHandState:
    def __init__(self, state = None):
        self.state = state
    
    def update_state(self, new_state: int, write_can_bus: Callable[[int, bytearray], None]):
        try:
            new_pos = SeedlingHandPosition(new_state)
        except ValueError as e:
            print(f"Error at SeedlingHandState.update_state {e}")
            return

        print(f"self.state = {self.state} and new_pos = {new_pos}")

        if self.state == new_pos:
            return

        if new_pos == SeedlingHandPosition.RESET:
            write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.RESET.value]))
            time.sleep(3)
            write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray(self.state.value))
            return

        if new_pos == SeedlingHandPosition.PICKUP:
            write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.PICKUP.value]))
        elif new_pos == SeedlingHandPosition.PUTINSIDE:
            write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.PUTINSIDE.value]))
        elif new_pos == SeedlingHandPosition.PUTOUTSIDE:
            write_can_bus(CANList.SEEDLING_HAND_POSITION.value, bytearray([SeedlingHandPosition.PUTOUTSIDE.value]))
            
        self.state = new_pos
        
    def set_btn_y_handler(self, write_can_bus: Callable[[int, bytearray], None]) -> Tuple[Callable[[], None], Callable[[], None]]:
        if self.state == SeedlingHandPosition.RESET:
            def action_send_0():
                pass
            def action_send_1():
                pass
        
        if self.state == SeedlingHandPosition.PICKUP:
            def action_send_0():
                write_can_bus(CANList.SEEDLING_INSIDE_HAND_OPEN.value, bytearray([0]))
                time.sleep(0.01)
                write_can_bus(CANList.SEEDLING_OUTSIDE_HAND_OPEN.value, bytearray([0]))
            
            def action_send_1():
                write_can_bus(CANList.SEEDLING_INSIDE_HAND_OPEN.value, bytearray([1]))
                time.sleep(0.01)
                write_can_bus(CANList.SEEDLING_OUTSIDE_HAND_OPEN.value, bytearray([1]))
            
            return (action_send_0, action_send_1)
        
        if self.state == SeedlingHandPosition.PUTINSIDE:
            def action_send_0():
                write_can_bus(CANList.SEEDLING_INSIDE_HAND_OPEN.value, bytearray([0]))
            
            def action_send_1():
                write_can_bus(CANList.SEEDLING_INSIDE_HAND_OPEN.value, bytearray([1]))
                
            return (action_send_0, action_send_1)
        
        if self.state == SeedlingHandPosition.PUTOUTSIDE:
            def action_send_0():
                write_can_bus(CANList.SEEDLING_OUTSIDE_HAND_OPEN.value, bytearray([0]))
            
            def action_send_1():
                write_can_bus(CANList.SEEDLING_OUTSIDE_HAND_OPEN.value, bytearray([1]))
            
            return (action_send_0, action_send_1)

    def reset_state(self, new_state: int):
        self.state = SeedlingHandPosition(new_state)