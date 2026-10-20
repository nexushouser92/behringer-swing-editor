import ctypes
from ctypes import wintypes
w=ctypes.windll.winmm
class INCAPS(ctypes.Structure):
    _fields_=[('wMid',wintypes.WORD),('wPid',wintypes.WORD),('v',wintypes.UINT),('name',ctypes.c_wchar*32),('sup',wintypes.DWORD)]
class OUTCAPS(ctypes.Structure):
    _fields_=[('wMid',wintypes.WORD),('wPid',wintypes.WORD),('v',wintypes.UINT),('name',ctypes.c_wchar*32),('t',wintypes.WORD),('vo',wintypes.WORD),('n',wintypes.WORD),('m',wintypes.WORD),('sup',wintypes.DWORD)]
for i in range(w.midiInGetNumDevs()):
    c=INCAPS(); w.midiInGetDevCapsW(i,ctypes.byref(c),ctypes.sizeof(c)); print('IN ',i,c.name)
for i in range(w.midiOutGetNumDevs()):
    c=OUTCAPS(); w.midiOutGetDevCapsW(i,ctypes.byref(c),ctypes.sizeof(c)); print('OUT',i,c.name)
