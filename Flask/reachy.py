

try:
    from reachy_sdk import ReachySDK
    from reachy_sdk.trajectory import goto
    from reachy_sdk.trajectory.interpolation import InterpolationMode
    REACHY_SDK_AVAILABLE = True
except ImportError:
    ReachySDK = None
    goto = None
    InterpolationMode = None
    REACHY_SDK_AVAILABLE = False
    