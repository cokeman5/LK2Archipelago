import random


def apply(patcher,output_data):
    offset = 0
    model_num = output_data.get("character_model",0)
    if model_num == 16:
        model_num = random.randint(0,15)
    match model_num:
        case 0:
            offset = 0x0
        case 1:
            offset = 0x1
        case 2:
            offset = 0x3
        case 3:
            offset = 0x6
        case 4:
            offset = 0x7
        case 5:
            offset = 0x8
        case 6:
            offset = 0x13
        case 7:
            offset = 0x24
        case 8:
            offset = 0x29
        case 9:
            offset = 0x2a
        case 10:
            offset = 0x2b
        case 11:
            offset = 0x2c
        case 12:
            offset = 0x2d
        case 13:
            offset = 0x2e
        case 14:
            offset = 0x2f
        case 15:
            offset = 0x30

    patcher.patch_word(0x8005332c,  0x38000000+offset)