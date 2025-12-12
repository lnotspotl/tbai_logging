# tbai_logging 

## Showcase

![434561804-2d2686af-d172-4585-a409-30bed890bb94](https://github.com/user-attachments/assets/872676c6-91b5-4d87-b072-50816e1853b1)

![434897918-bb4aea85-e036-43d1-805c-7d5761582ebd](https://github.com/user-attachments/assets/e50be988-0492-48b0-93d9-c2e7a87d9fd1)


## Zoo



There are many robots in the zoo and we rely on the amazing [robot_descriptions.py](https://github.com/robot-descriptions/robot_descriptions.py) project that does the model downloading and loading on our behalf.

```python3
from tbai_logging.robot_zoo import all_robots
from tbai_logging.robot_zoo import get_robot_model

print(all_robots())

```

```python3
from tbai_logging.rerun.robot_logger import RobotLogger
go2_logger = RobotLogger.from_zoo("go2_description", prefix="go2")
g1_logger = RobotLogger.from_zoo("g1_description", prefix="g1")
```

## Install

Install directly from GitHub:
```bash
pip3 install git+https://github.com/lnotspotl/tbai_logging.git
```

Or clone and install in editable mode for development:
```bash
git clone git@github.com:lnotspotl/tbai_logging.git && cd tbai_logging
pip3 install -e .
```

## TODOs

- [x] Switch completely to pinocchio, use nothing else but pinocchio


<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">
  <img src="https://github.com/user-attachments/assets/8c5fc2c8-dc1f-4b16-89be-b0072c97eb9d" alt="backflip" style="width: 350px; height: 350px;">
  <img src="https://github.com/user-attachments/assets/5666116a-9fed-4074-9169-b1834b218cf7" alt="frontjump" style="width: 350px; height: 350px;">
</div>
