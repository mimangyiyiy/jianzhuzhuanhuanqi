# -*- coding: utf-8 -*-
"""MC 建筑转换器 - Pyodide Web 核心模块 (精简版)"""
# 自动提取自 jz.py


# ==== lines 9-27 ====
import sys
import os
# PyInstaller EXE console UTF-8 fix
if os.name == "nt":
    try:
        import ctypes; ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception: pass
import io
import math
import struct
import gzip
import zlib
import zipfile
import random
import hashlib
import base64
import subprocess
from pathlib import Path
from collections import defaultdict

from sensitive_filter import SensitiveFilter
_SF = SensitiveFilter()

# ==== lines 73-82 ====
def _sanitize_name(name):
    if _SF is None or not _SF.contains(name):
        return name
    return name  # Pyodide: 简易过滤，保留原名

# ==== lines 92-257 ====
class NBTReader:
    """ Minecraft NBT """
    
    def __init__(self, data):
        self.data = data
        self.offset = 0
    
    def read_byte(self):
        if self.offset >= len(self.data):
            raise ValueError("NBT  ()")
        v = self.data[self.offset]
        self.offset += 1
        return v

    def skip_tag(self, tag_type):
        """ value ()"""
        if tag_type == 0:
            return
        elif tag_type == 1:
            self.offset += 1
        elif tag_type == 2:
            self.offset += 2
        elif tag_type == 3:
            self.offset += 4
        elif tag_type == 4:
            self.offset += 8
        elif tag_type == 5:
            self.offset += 4
        elif tag_type == 6:
            self.offset += 8
        elif tag_type == 7:  # TAG_Byte_Array
            length = self.read_int()
            self.offset += length
        elif tag_type == 8:  # TAG_String
            length = self.read_short()
            self.offset += length
        elif tag_type == 9:  # TAG_List
            et = self.read_byte()
            length = self.read_int()
            for _ in range(length):
                self.skip_tag(et)
        elif tag_type == 10:  # TAG_Compound
            while True:
                ct = self.read_byte()
                if ct == 0:
                    return
                self.read_string()
                self.skip_tag(ct)
        elif tag_type == 11:  # TAG_Int_Array
            length = self.read_int()
            self.offset += length * 4
        elif tag_type == 12:  # TAG_Long_Array
            length = self.read_int()
            self.offset += length * 8
        else:
            raise ValueError(f" NBT : {tag_type}")
    
    def read_short(self):
        v = struct.unpack('>h', self.data[self.offset:self.offset+2])[0]
        self.offset += 2
        return v
    
    def read_int(self):
        v = struct.unpack('>i', self.data[self.offset:self.offset+4])[0]
        self.offset += 4
        return v
    
    def read_long(self):
        v = struct.unpack('>q', self.data[self.offset:self.offset+8])[0]
        self.offset += 8
        return v
    
    def read_float(self):
        v = struct.unpack('>f', self.data[self.offset:self.offset+4])[0]
        self.offset += 4
        return v
    
    def read_double(self):
        v = struct.unpack('>d', self.data[self.offset:self.offset+8])[0]
        self.offset += 8
        return v
    
    def read_string(self):
        length = self.read_short()
        v = self.data[self.offset:self.offset+length].decode('utf-8')
        self.offset += length
        return v
    
    def read_byte_array(self):
        length = self.read_int()
        v = self.data[self.offset:self.offset+length]
        self.offset += length
        return v
    
    def read_int_array(self):
        length = self.read_int()
        v = []
        for _ in range(length):
            v.append(self.read_int())
        return v
    
    def read_long_array(self):
        length = self.read_int()
        v = []
        for _ in range(length):
            v.append(self.read_long())
        return v
    
    def read_compound(self):
        data = {}
        while True:
            tag_type = self.read_byte()
            if tag_type == 0:  # TAG_End
                break
            name = self.read_string()
            data[name] = self.read_tag(tag_type)
        return data

    def read_root(self):
        """ NBT  ( + ), (dict)

        : NBT  [][][]
        read_compound() , ,
        , 
        """
        root_type = self.read_byte()
        if root_type != 10:
            raise ValueError(f"NBT  TAG_Compound(10),  {root_type}")
        self.read_string()  #  ( ''  'Schematic'/'Level')
        return self.read_tag(root_type)
    
    def read_list(self):
        tag_type = self.read_byte()
        length = self.read_int()
        result = []
        for _ in range(length):
            result.append(self.read_tag(tag_type))
        return result
    
    def read_tag(self, tag_type):
        if tag_type == 1:   # TAG_Byte
            return self.read_byte()
        elif tag_type == 2: # TAG_Short
            return self.read_short()
        elif tag_type == 3: # TAG_Int
            return self.read_int()
        elif tag_type == 4: # TAG_Long
            return self.read_long()
        elif tag_type == 5: # TAG_Float
            return self.read_float()
        elif tag_type == 6: # TAG_Double
            return self.read_double()
        elif tag_type == 7: # TAG_Byte_Array
            return self.read_byte_array()
        elif tag_type == 8: # TAG_String
            return self.read_string()
        elif tag_type == 9: # TAG_List
            return self.read_list()
        elif tag_type == 10: # TAG_Compound
            return self.read_compound()
        elif tag_type == 11: # TAG_Int_Array
            return self.read_int_array()
        elif tag_type == 12: # TAG_Long_Array
            return self.read_long_array()
        else:
            raise ValueError(f" NBT : {tag_type}")

# ==== lines 264-575 ====
LEGACY_BLOCKS = {
    0: ('minecraft:air', {}),
    1: ('minecraft:stone', {0: 'minecraft:stone', 1: 'minecraft:granite', 2: 'minecraft:polished_granite',
                            3: 'minecraft:diorite', 4: 'minecraft:polished_diorite',
                            5: 'minecraft:andesite', 6: 'minecraft:polished_andesite'}),
    2: ('minecraft:grass_block', {}),
    3: ('minecraft:dirt', {0: 'minecraft:dirt', 1: 'minecraft:coarse_dirt', 2: 'minecraft:podzol'}),
    4: ('minecraft:cobblestone', {}),
    5: ('minecraft:oak_planks', {0: 'minecraft:oak_planks', 1: 'minecraft:spruce_planks',
                                  2: 'minecraft:birch_planks', 3: 'minecraft:jungle_planks',
                                  4: 'minecraft:acacia_planks', 5: 'minecraft:dark_oak_planks'}),
    6: ('minecraft:sapling', {}),
    7: ('minecraft:bedrock', {}),
    8: ('minecraft:water', {}),
    9: ('minecraft:water', {}),
    10: ('minecraft:lava', {}),
    11: ('minecraft:lava', {}),
    12: ('minecraft:sand', {0: 'minecraft:sand', 1: 'minecraft:red_sand'}),
    13: ('minecraft:gravel', {}),
    14: ('minecraft:gold_ore', {}),
    15: ('minecraft:iron_ore', {}),
    16: ('minecraft:coal_ore', {}),
    17: ('minecraft:oak_log', {0: 'minecraft:oak_log', 1: 'minecraft:spruce_log',
                              2: 'minecraft:birch_log', 3: 'minecraft:jungle_log'}),
    18: ('minecraft:oak_leaves', {0: 'minecraft:oak_leaves', 1: 'minecraft:spruce_leaves',
                                 2: 'minecraft:birch_leaves', 3: 'minecraft:jungle_leaves'}),
    19: ('minecraft:sponge', {}),
    20: ('minecraft:glass', {}),
    21: ('minecraft:lapis_ore', {}),
    22: ('minecraft:lapis_block', {}),
    23: ('minecraft:dispenser', {}),
    24: ('minecraft:sandstone', {0: 'minecraft:sandstone', 1: 'minecraft:chiseled_sandstone',
                                 2: 'minecraft:cut_sandstone'}),
    25: ('minecraft:note_block', {}),
    26: ('minecraft:bed', {}),
    27: ('minecraft:golden_rail', {}),
    28: ('minecraft:detector_rail', {}),
    29: ('minecraft:sticky_piston', {}),
    30: ('minecraft:web', {}),
    31: ('minecraft:tallgrass', {0: 'minecraft:dead_bush', 1: 'minecraft:tallgrass', 2: 'minecraft:fern'}),
    32: ('minecraft:deadbush', {}),
    33: ('minecraft:piston', {}),
    34: ('minecraft:piston_head', {}),
    35: ('minecraft:white_wool', {0: 'minecraft:white_wool', 1: 'minecraft:orange_wool', 2: 'minecraft:magenta_wool',
                                  3: 'minecraft:light_blue_wool', 4: 'minecraft:yellow_wool', 5: 'minecraft:lime_wool',
                                  6: 'minecraft:pink_wool', 7: 'minecraft:gray_wool', 8: 'minecraft:light_gray_wool',
                                  9: 'minecraft:cyan_wool', 10: 'minecraft:purple_wool', 11: 'minecraft:blue_wool',
                                  12: 'minecraft:brown_wool', 13: 'minecraft:green_wool', 14: 'minecraft:red_wool',
                                  15: 'minecraft:black_wool'}),
    37: ('minecraft:red_flower', {}),
    38: ('minecraft:blue_orchid', {}),
    39: ('minecraft:brown_mushroom', {}),
    40: ('minecraft:red_mushroom', {}),
    41: ('minecraft:gold_block', {}),
    42: ('minecraft:iron_block', {}),
    43: ('minecraft:stone_slab', {0: 'minecraft:stone_slab', 1: 'minecraft:sandstone_slab', 2: 'minecraft:wooden_slab',
                                  3: 'minecraft:cobblestone_slab', 4: 'minecraft:brick_slab', 5: 'minecraft:stone_brick_slab',
                                  6: 'minecraft:nether_brick_slab', 7: 'minecraft:quartz_slab'}),
    44: ('minecraft:stone_slab', {0: 'minecraft:stone_slab', 1: 'minecraft:sandstone_slab', 2: 'minecraft:wooden_slab',
                                  3: 'minecraft:cobblestone_slab', 4: 'minecraft:brick_slab', 5: 'minecraft:stone_brick_slab',
                                  6: 'minecraft:nether_brick_slab', 7: 'minecraft:quartz_slab'}),
    45: ('minecraft:brick_block', {}),
    46: ('minecraft:tnt', {}),
    47: ('minecraft:bookshelf', {}),
    48: ('minecraft:mossy_cobblestone', {}),
    49: ('minecraft:obsidian', {}),
    50: ('minecraft:torch', {}),
    51: ('minecraft:fire', {}),
    52: ('minecraft:spawner', {}),
    53: ('minecraft:oak_stairs', {}),
    54: ('minecraft:chest', {}),
    55: ('minecraft:redstone_wire', {}),
    56: ('minecraft:diamond_ore', {}),
    57: ('minecraft:diamond_block', {}),
    58: ('minecraft:crafting_table', {}),
    59: ('minecraft:wheat', {}),
    60: ('minecraft:farmland', {}),
    61: ('minecraft:furnace', {}),
    62: ('minecraft:lit_furnace', {}),
    63: ('minecraft:standing_sign', {}),
    64: ('minecraft:wooden_door', {}),
    65: ('minecraft:ladder', {}),
    66: ('minecraft:rail', {}),
    67: ('minecraft:cobblestone_stairs', {}),
    68: ('minecraft:wall_sign', {}),
    69: ('minecraft:lever', {}),
    70: ('minecraft:stone_pressure_plate', {}),
    71: ('minecraft:iron_door', {}),
    72: ('minecraft:wooden_pressure_plate', {}),
    73: ('minecraft:redstone_ore', {}),
    74: ('minecraft:lit_redstone_ore', {}),
    75: ('minecraft:unlit_redstone_torch', {}),
    76: ('minecraft:redstone_torch', {}),
    77: ('minecraft:stone_button', {}),
    78: ('minecraft:snow_layer', {}),
    79: ('minecraft:ice', {}),
    80: ('minecraft:snow', {}),
    81: ('minecraft:cactus', {}),
    82: ('minecraft:clay', {}),
    83: ('minecraft:reeds', {}),
    84: ('minecraft:jukebox', {}),
    85: ('minecraft:oak_fence', {}),
    86: ('minecraft:pumpkin', {}),
    87: ('minecraft:netherrack', {}),
    88: ('minecraft:soul_sand', {}),
    89: ('minecraft:glowstone', {}),
    90: ('minecraft:portal', {}),
    91: ('minecraft:jack_o_lantern', {}),
    92: ('minecraft:cake', {}),
    93: ('minecraft:repeater', {}),
    94: ('minecraft:powered_repeater', {}),
    95: ('minecraft:stained_glass', {0: 'minecraft:white_stained_glass', 1: 'minecraft:orange_stained_glass',
                                     2: 'minecraft:magenta_stained_glass', 3: 'minecraft:light_blue_stained_glass',
                                     4: 'minecraft:yellow_stained_glass', 5: 'minecraft:lime_stained_glass',
                                     6: 'minecraft:pink_stained_glass', 7: 'minecraft:gray_stained_glass',
                                     8: 'minecraft:light_gray_stained_glass', 9: 'minecraft:cyan_stained_glass',
                                     10: 'minecraft:purple_stained_glass', 11: 'minecraft:blue_stained_glass',
                                     12: 'minecraft:brown_stained_glass', 13: 'minecraft:green_stained_glass',
                                     14: 'minecraft:red_stained_glass', 15: 'minecraft:black_stained_glass'}),
    96: ('minecraft:trapdoor', {}),
    97: ('minecraft:monster_egg', {}),
    98: ('minecraft:stone_bricks', {0: 'minecraft:stone_bricks', 1: 'minecraft:mossy_stone_bricks',
                                    2: 'minecraft:cracked_stone_bricks', 3: 'minecraft:chiseled_stone_bricks'}),
    99: ('minecraft:brown_mushroom_block', {}),
    100: ('minecraft:red_mushroom_block', {}),
    101: ('minecraft:iron_bars', {}),
    102: ('minecraft:glass_pane', {}),
    103: ('minecraft:melon_block', {}),
    104: ('minecraft:pumpkin_stem', {}),
    105: ('minecraft:melon_stem', {}),
    106: ('minecraft:vine', {}),
    107: ('minecraft:fence_gate', {}),
    108: ('minecraft:brick_stairs', {}),
    109: ('minecraft:stone_brick_stairs', {}),
    110: ('minecraft:mycelium', {}),
    111: ('minecraft:waterlily', {}),
    112: ('minecraft:nether_brick', {}),
    113: ('minecraft:nether_brick_fence', {}),
    114: ('minecraft:nether_brick_stairs', {}),
    115: ('minecraft:nether_wart', {}),
    116: ('minecraft:enchanting_table', {}),
    117: ('minecraft:brewing_stand', {}),
    118: ('minecraft:cauldron', {}),
    119: ('minecraft:end_portal', {}),
    120: ('minecraft:end_portal_frame', {}),
    121: ('minecraft:end_stone', {}),
    122: ('minecraft:dragon_egg', {}),
    123: ('minecraft:redstone_lamp', {}),
    124: ('minecraft:lit_redstone_lamp', {}),
    125: ('minecraft:wooden_slab', {0: 'minecraft:oak_slab', 1: 'minecraft:spruce_slab', 2: 'minecraft:birch_slab',
                                    3: 'minecraft:jungle_slab', 4: 'minecraft:acacia_slab', 5: 'minecraft:dark_oak_slab'}),
    126: ('minecraft:wooden_slab', {0: 'minecraft:oak_slab', 1: 'minecraft:spruce_slab', 2: 'minecraft:birch_slab',
                                    3: 'minecraft:jungle_slab', 4: 'minecraft:acacia_slab', 5: 'minecraft:dark_oak_slab'}),
    127: ('minecraft:cocoa', {}),
    128: ('minecraft:sandstone_stairs', {}),
    129: ('minecraft:emerald_ore', {}),
    130: ('minecraft:ender_chest', {}),
    131: ('minecraft:tripwire_hook', {}),
    132: ('minecraft:tripwire', {}),
    133: ('minecraft:emerald_block', {}),
    134: ('minecraft:spruce_stairs', {}),
    135: ('minecraft:birch_stairs', {}),
    136: ('minecraft:jungle_stairs', {}),
    137: ('minecraft:command_block', {}),
    138: ('minecraft:beacon', {}),
    139: ('minecraft:stone_wall', {}),
    140: ('minecraft:flower_pot', {}),
    141: ('minecraft:carrot', {}),
    142: ('minecraft:potato', {}),
    143: ('minecraft:wooden_button', {}),
    144: ('minecraft:skull', {}),
    145: ('minecraft:anvil', {}),
    146: ('minecraft:trapped_chest', {}),
    147: ('minecraft:weighted_pressure_plate_light', {}),
    148: ('minecraft:weighted_pressure_plate_heavy', {}),
    149: ('minecraft:daylight_detector', {}),
    150: ('minecraft:redstone_block', {}),
    151: ('minecraft:quartz_ore', {}),
    152: ('minecraft:hopper', {}),
    153: ('minecraft:quartz_block', {0: 'minecraft:quartz_block', 1: 'minecraft:chiseled_quartz_block',
                                     2: 'minecraft:quartz_pillar'}),
    154: ('minecraft:quartz_stairs', {}),
    155: ('minecraft:activator_rail', {}),
    156: ('minecraft:dropper', {}),
    157: ('minecraft:white_stained_hardened_clay', {0: 'minecraft:white_terracotta', 1: 'minecraft:orange_terracotta',
                                                    2: 'minecraft:magenta_terracotta', 3: 'minecraft:light_blue_terracotta',
                                                    4: 'minecraft:yellow_terracotta', 5: 'minecraft:lime_terracotta',
                                                    6: 'minecraft:pink_terracotta', 7: 'minecraft:gray_terracotta',
                                                    8: 'minecraft:light_gray_terracotta', 9: 'minecraft:cyan_terracotta',
                                                    10: 'minecraft:purple_terracotta', 11: 'minecraft:blue_terracotta',
                                                    12: 'minecraft:brown_terracotta', 13: 'minecraft:green_terracotta',
                                                    14: 'minecraft:red_terracotta', 15: 'minecraft:black_terracotta'}),
    158: ('minecraft:hay_block', {}),
    159: ('minecraft:white_terracotta', {0: 'minecraft:white_terracotta', 1: 'minecraft:orange_terracotta',
                                         2: 'minecraft:magenta_terracotta', 3: 'minecraft:light_blue_terracotta',
                                         4: 'minecraft:yellow_terracotta', 5: 'minecraft:lime_terracotta',
                                         6: 'minecraft:pink_terracotta', 7: 'minecraft:gray_terracotta',
                                         8: 'minecraft:light_gray_terracotta', 9: 'minecraft:cyan_terracotta',
                                         10: 'minecraft:purple_terracotta', 11: 'minecraft:blue_terracotta',
                                         12: 'minecraft:brown_terracotta', 13: 'minecraft:green_terracotta',
                                         14: 'minecraft:red_terracotta', 15: 'minecraft:black_terracotta'}),
    160: ('minecraft:white_stained_glass_pane', {}),
    161: ('minecraft:acacia_leaves', {0: 'minecraft:acacia_leaves', 1: 'minecraft:dark_oak_leaves'}),
    162: ('minecraft:acacia_log', {0: 'minecraft:acacia_log', 1: 'minecraft:dark_oak_log'}),
    163: ('minecraft:acacia_stairs', {}),
    164: ('minecraft:dark_oak_stairs', {}),
    165: ('minecraft:slime_block', {}),
    166: ('minecraft:barrier', {}),
    167: ('minecraft:iron_trapdoor', {}),
    168: ('minecraft:prismarine', {0: 'minecraft:prismarine', 1: 'minecraft:prismarine_bricks',
                                   2: 'minecraft:dark_prismarine'}),
    169: ('minecraft:sea_lantern', {}),
    170: ('minecraft:hay_block', {}),
    171: ('minecraft:carpet', {0: 'minecraft:white_carpet', 1: 'minecraft:orange_carpet', 2: 'minecraft:magenta_carpet',
                               3: 'minecraft:light_blue_carpet', 4: 'minecraft:yellow_carpet', 5: 'minecraft:lime_carpet',
                               6: 'minecraft:pink_carpet', 7: 'minecraft:gray_carpet', 8: 'minecraft:light_gray_carpet',
                               9: 'minecraft:cyan_carpet', 10: 'minecraft:purple_carpet', 11: 'minecraft:blue_carpet',
                               12: 'minecraft:brown_carpet', 13: 'minecraft:green_carpet', 14: 'minecraft:red_carpet',
                               15: 'minecraft:black_carpet'}),
    172: ('minecraft:hardened_clay', {}),
    173: ('minecraft:coal_block', {}),
    174: ('minecraft:packed_ice', {}),
    175: ('minecraft:double_plant', {}),
    179: ('minecraft:red_sandstone', {0: 'minecraft:red_sandstone', 1: 'minecraft:chiseled_red_sandstone',
                                      2: 'minecraft:cut_red_sandstone'}),
    180: ('minecraft:red_sandstone_stairs', {}),
    181: ('minecraft:double_stone_slab2', {}),
    182: ('minecraft:red_sandstone_slab', {}),
    183: ('minecraft:spruce_fence_gate', {}),
    184: ('minecraft:birch_fence_gate', {}),
    185: ('minecraft:jungle_fence_gate', {}),
    186: ('minecraft:dark_oak_fence_gate', {}),
    187: ('minecraft:acacia_fence_gate', {}),
    188: ('minecraft:spruce_fence', {}),
    189: ('minecraft:birch_fence', {}),
    190: ('minecraft:jungle_fence', {}),
    191: ('minecraft:dark_oak_fence', {}),
    192: ('minecraft:acacia_fence', {}),
    193: ('minecraft:spruce_door', {}),
    194: ('minecraft:birch_door', {}),
    195: ('minecraft:jungle_door', {}),
    196: ('minecraft:acacia_door', {}),
    197: ('minecraft:dark_oak_door', {}),
    198: ('minecraft:end_rod', {}),
    199: ('minecraft:chorus_plant', {}),
    200: ('minecraft:chorus_flower', {}),
    201: ('minecraft:purpur_block', {}),
    202: ('minecraft:purpur_pillar', {}),
    203: ('minecraft:purpur_stairs', {}),
    204: ('minecraft:purpur_slab', {}),
    205: ('minecraft:end_stone_bricks', {}),
    206: ('minecraft:beetroot', {}),
    207: ('minecraft:grass_path', {}),
    208: ('minecraft:end_gateway', {}),
    209: ('minecraft:repeating_command_block', {}),
    210: ('minecraft:chain_command_block', {}),
    211: ('minecraft:frosted_ice', {}),
    212: ('minecraft:magma_block', {}),
    213: ('minecraft:nether_wart_block', {}),
    214: ('minecraft:red_nether_brick', {}),
    215: ('minecraft:bone_block', {}),
    216: ('minecraft:structure_void', {}),
    217: ('minecraft:observer', {}),
    218: ('minecraft:white_shulker_box', {}),
    219: ('minecraft:orange_shulker_box', {}),
    220: ('minecraft:magenta_shulker_box', {}),
    221: ('minecraft:light_blue_shulker_box', {}),
    222: ('minecraft:yellow_shulker_box', {}),
    223: ('minecraft:lime_shulker_box', {}),
    224: ('minecraft:pink_shulker_box', {}),
    225: ('minecraft:gray_shulker_box', {}),
    226: ('minecraft:light_gray_shulker_box', {}),
    227: ('minecraft:cyan_shulker_box', {}),
    228: ('minecraft:purple_shulker_box', {}),
    229: ('minecraft:blue_shulker_box', {}),
    230: ('minecraft:brown_shulker_box', {}),
    231: ('minecraft:green_shulker_box', {}),
    232: ('minecraft:red_shulker_box', {}),
    233: ('minecraft:black_shulker_box', {}),
    234: ('minecraft:white_glazed_terracotta', {}),
    235: ('minecraft:orange_glazed_terracotta', {}),
    236: ('minecraft:magenta_glazed_terracotta', {}),
    237: ('minecraft:light_blue_glazed_terracotta', {}),
    238: ('minecraft:yellow_glazed_terracotta', {}),
    239: ('minecraft:lime_glazed_terracotta', {}),
    240: ('minecraft:pink_glazed_terracotta', {}),
    241: ('minecraft:gray_glazed_terracotta', {}),
    242: ('minecraft:light_gray_glazed_terracotta', {}),
    243: ('minecraft:cyan_glazed_terracotta', {}),
    244: ('minecraft:purple_glazed_terracotta', {}),
    245: ('minecraft:blue_glazed_terracotta', {}),
    246: ('minecraft:brown_glazed_terracotta', {}),
    247: ('minecraft:green_glazed_terracotta', {}),
    248: ('minecraft:red_glazed_terracotta', {}),
    249: ('minecraft:black_glazed_terracotta', {}),
    250: ('minecraft:concrete', {0: 'minecraft:white_concrete', 1: 'minecraft:orange_concrete', 2: 'minecraft:magenta_concrete',
                                 3: 'minecraft:light_blue_concrete', 4: 'minecraft:yellow_concrete', 5: 'minecraft:lime_concrete',
                                 6: 'minecraft:pink_concrete', 7: 'minecraft:gray_concrete', 8: 'minecraft:light_gray_concrete',
                                 9: 'minecraft:cyan_concrete', 10: 'minecraft:purple_concrete', 11: 'minecraft:blue_concrete',
                                 12: 'minecraft:brown_concrete', 13: 'minecraft:green_concrete', 14: 'minecraft:red_concrete',
                                 15: 'minecraft:black_concrete'}),
    251: ('minecraft:concrete_powder', {0: 'minecraft:white_concrete_powder', 1: 'minecraft:orange_concrete_powder',
                                        2: 'minecraft:magenta_concrete_powder', 3: 'minecraft:light_blue_concrete_powder',
                                        4: 'minecraft:yellow_concrete_powder', 5: 'minecraft:lime_concrete_powder',
                                        6: 'minecraft:pink_concrete_powder', 7: 'minecraft:gray_concrete_powder',
                                        8: 'minecraft:light_gray_concrete_powder', 9: 'minecraft:cyan_concrete_powder',
                                        10: 'minecraft:purple_concrete_powder', 11: 'minecraft:blue_concrete_powder',
                                        12: 'minecraft:brown_concrete_powder', 13: 'minecraft:green_concrete_powder',
                                        14: 'minecraft:red_concrete_powder', 15: 'minecraft:black_concrete_powder'}),
    252: ('minecraft:structure_block', {}),
    255: ('minecraft:structure_block', {}),
}

# ==== lines 578-584 ====
def legacy_block_name(bid, data=0):
    """ numeric ID + data """
    entry = LEGACY_BLOCKS.get(bid)
    if entry is None:
        return None  # 
    default, variants = entry
    return variants.get(data, default)

# ==== lines 587-599 ====
def _read_varint(data, i):
    """ Minecraft VarInt (value, new_index)"""
    value = 0
    shift = 0
    while i < len(data):
        byte = data[i]
        i += 1
        value |= (byte & 0x7F) << shift
        if byte & 0x80 == 0:
            break
        shift += 7
    return value, i


# ==== lines 601-616 ====
def _decompress_nbt(raw):
    """ gzip / zlib /  NBT """
    if raw[:2] == b'\x1f\x8b':
        try:
            return gzip.decompress(raw)
        except Exception:
            pass
    try:
        return zlib.decompress(raw)
    except Exception:
        return raw


# =============================================================
# 1.6 Anvil  (.mca)  —  MCEdit/Axiom  ZIP
# =============================================================

# ==== lines 618-667 ====
def _parse_anvil_chunk(chunk_bytes):
    """ Anvil chunk  NBT [(wx,wy,wz,name)]"""
    try:
        nbt = _decompress_nbt(chunk_bytes)
        root = NBTReader(nbt).read_root()
        level = root.get('Level', {})
        cx = level.get('xPos', 0)
        cz = level.get('zPos', 0)
        sections = level.get('Sections', [])
        blocks = []
        for sec in sections:
            sy = sec.get('Y', 0)
            states = sec.get('BlockStates', [])
            palette = sec.get('Palette', [])
            if not palette:
                continue
            bits = max(4, (len(palette) - 1).bit_length())
            longs = states if isinstance(states, list) else []
            if not longs:
                continue
            mask = (1 << bits) - 1
            for y in range(16):
                for z in range(16):
                    for x in range(16):
                        idx = (y * 16 + z) * 16 + x
                        bit_off = idx * bits
                        arr_off = bit_off // 64
                        bit_in = bit_off % 64
                        val = 0
                        #  long  bits  (little-endian)
                        remaining = bits
                        cur = arr_off
                        boff = bit_in
                        while remaining > 0:
                            take = min(remaining, 64 - boff)
                            chunk = (longs[cur] >> boff) & ((1 << take) - 1)
                            val |= chunk << (bits - remaining)
                            remaining -= take
                            cur += 1
                            boff = 0
                        if val < 0 or val >= len(palette):
                            continue
                        pal = palette[val]
                        name = pal.get('Name', '') if isinstance(pal, dict) else ''
                        if name and name != 'minecraft:air':
                            blocks.append((cx * 16 + x, sy * 16 + y, cz * 16 + z, name))
        return blocks
    except Exception:
        return []


# ==== lines 669-691 ====
def _parse_region(region_bytes):
    """ .mca  [(wx,wy,wz,name)]"""
    blocks = []
    # :  4096 
    for cx in range(32):
        for cz in range(32):
            off = (cx + cz * 32) * 4
            loc = struct.unpack('>I', region_bytes[off:off + 4])[0]
            sector = (loc >> 8) & 0xFFFFFF
            if sector == 0:
                continue
            base = sector * 4096
            length = struct.unpack('>I', region_bytes[base:base + 4])[0]
            comp = region_bytes[base + 4]
            # : 4() + 1 + 
            #  = length - 1,  base+5 ,  base+4+length 
            chunk = region_bytes[base + 5:base + 4 + length]
            if comp == 1:
                chunk = gzip.decompress(chunk)
            elif comp == 2:
                chunk = zlib.decompress(chunk)
            blocks.extend(_parse_anvil_chunk(chunk))
    return blocks

# ==== lines 694-749 ====
def parse_zip_schematic(raw):
    """ ZIP  schematic (MCEdit/Axiom: schematic.dat + region/*.mca)"""
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = z.namelist()

    # 
    width = height = length = 0
    if 'schematic.dat' in names:
        sd = z.read('schematic.dat')
        try:
            sd = _decompress_nbt(sd)
            meta = NBTReader(sd).read_root()
            width = meta.get('Width', 0)
            height = meta.get('Height', 0)
            length = meta.get('Length', 0)
        except Exception:
            pass

    region_files = [n for n in names if n.endswith('.mca')]
    if not region_files:
        raise ValueError("ZIP  .mca ")

    print(f"  ZIP/MCEdit  ( {len(region_files)} )")

    all_blocks = []
    min_x = min_z = None
    for rf in region_files:
        rb = z.read(rf)
        sec_blocks = _parse_region(rb)
        for (wx, wy, wz, name) in sec_blocks:
            if min_x is None or wx < min_x:
                min_x = wx
            if min_z is None or wz < min_z:
                min_z = wz
        all_blocks.extend(sec_blocks)

    #  ()
    blocks = []
    for (wx, wy, wz, name) in all_blocks:
        blocks.append({
            'x': wx - (min_x or 0),
            'y': wy,
            'z': wz - (min_z or 0),
            'id': name if name.startswith('minecraft:') else f'minecraft:{name}'
        })

    #  schematic.dat 
    if not width or not length:
        max_x = max((b['x'] for b in blocks), default=0)
        max_z = max((b['z'] for b in blocks), default=0)
        width = max_x + 1
        length = max_z + 1
    if not height:
        height = max((b['y'] for b in blocks), default=0) + 1

    return blocks, width, height, length

# ==== lines 752-832 ====
def parse_schematic(file_path):
    """ .schematic  (, , , )

    :
      1.  WorldEdit (.schematic, GZIP, Blocks+Data  + numeric ID)
      2.  WorldEdit (.schematic, GZIP, Palette + BlockData )
      3. MCEdit/Axiom (ZIP, schematic.dat + region/*.mca Anvil )
    """
    print("读取文件...", flush=True)
    with open(file_path, 'rb') as f:
        raw_data = f.read()
    print(f"   文件大小: {len(raw_data):,} 字节", flush=True)

    # 1) ZIP  (MCEdit/Axiom)
    if raw_data[:2] == b'PK':
        return parse_zip_schematic(raw_data)

    # 2) GZIP /  NBT
    try:
        data = _decompress_nbt(raw_data)
        root = NBTReader(data).read_root()
    except (ValueError, struct.error) as e:
        raise ValueError(f"无法解析 .schematic 文件（不是有效的 NBT 格式）: {e}")

    width = root.get('Width', 0) or 0
    height = root.get('Height', 0) or 0
    length = root.get('Length', 0) or 0

    print(f" [2/4] 尺寸: {width} × {height} × {length}", flush=True)

    blocks_raw = root.get('Blocks', b'')
    data_raw = root.get('Data', b'')
    palette = root.get('Palette', {})
    block_data = root.get('BlockData', [])

    blocks = []

    if palette and block_data:
        #  (1.13+): Palette + BlockData (VarInt)
        print(" [3/4] 解析 Palette + BlockData ", flush=True)
        palette_list = [''] * (max(palette.values(), default=-1) + 1)
        for name, idx in palette.items():
            if 0 <= idx < len(palette_list):
                palette_list[idx] = name
        block_ids = []
        i = 0
        total = width * height * length
        while i < len(block_data) and len(block_ids) < total:
            value, i = _read_varint(block_data, i)
            name = palette_list[value] if value < len(palette_list) else ''
            block_ids.append(name)
        idx = 0
        for y in range(height):
            for z in range(length):
                for x in range(width):
                    name = block_ids[idx] if idx < len(block_ids) else ''
                    idx += 1
                    if name and name != 'minecraft:air':
                        blocks.append({'x': x, 'y': y, 'z': z, 'id': name})
    else:
        #  (1.12-): Blocks(ID) + Data()
        print(" [3/4] 解析 Blocks + Data ", flush=True)
        n = width * height * length
        for idx in range(n):
            bid = blocks_raw[idx] if idx < len(blocks_raw) else 0
            if bid == 0:
                continue
            d = data_raw[idx] if idx < len(data_raw) else 0
            name = legacy_block_name(bid, d)
            if name is None:
                continue
            name = _add_data_state(name, bid, d)
            # : idx = (y*length + z)*width + x
            y = idx // (length * width)
            rem = idx % (length * width)
            z = rem // width
            x = rem % width
            blocks.append({'x': x, 'y': y, 'z': z, 'id': name})

    print(f" [4/4] 方块数: {len(blocks):,} ", flush=True)
    return blocks, width, height, length

# ==== lines 835-929 ====
def parse_litematic(file_path):
    """解析 .litematic 文件 (Litematica 模组格式)"""
    print("读取 .litematic 文件...", flush=True)
    with open(file_path, 'rb') as f:
        raw = f.read()
    print(f"   文件大小: {len(raw):,} 字节", flush=True)
    data = _decompress_nbt(raw)
    root = NBTReader(data).read_root()
    regions = root.get('Regions', {}) or {}
    if not regions and 'Minecraft' in root:
        mc = root['Minecraft']
        if isinstance(mc, dict):
            regions = mc.get('Regions', {}) or {}
    if not regions:
        if isinstance(root.get('Regions'), list):
            regions = {f"region_{i}": r for i, r in enumerate(root['Regions'])}
        if not regions:
            raise ValueError(f"未找到 Regions，文件根键: {list(root.keys())}")

    def _extract_xyz(value):
        """从 list [x,y,z] 或 dict {x:,y:,z:} 提取 x,y,z 三元组"""
        if isinstance(value, dict):
            return int(value.get('x', 0)), int(value.get('y', 0)), int(value.get('z', 0))
        elif isinstance(value, (list, tuple)):
            return int(value[0]), int(value[1]), int(value[2])
        raise ValueError(f"无法解析xyz: {type(value)}")

    blocks = []
    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')
    for rname, region in regions.items():
        if not isinstance(region, dict):
            continue
        pos_raw = region.get('Position', [0, 0, 0])
        size_raw = region.get('Size', [0, 0, 0])
        palette_raw = region.get('BlockStatePalette', [])
        states_raw = region.get('BlockStates', [])
        if not size_raw or not palette_raw:
            continue
        try:
            sx, sy, sz = _extract_xyz(size_raw)
            sx, sy, sz = abs(sx), abs(sy), abs(sz)
            rx, ry, rz = _extract_xyz(pos_raw)
        except (ValueError, TypeError):
            continue
        psize = len(palette_raw)
        bits = max(2, (psize - 1).bit_length())
        mask = (1 << bits) - 1
        total = sx * sy * sz
        print(f"   区域 '{rname}': {sx}x{sy}x{sz}, 调色板={psize}, 偏移=({rx},{ry},{rz})", flush=True)
        idx = 0
        for by in range(sy):
            for bz in range(sz):
                for bx in range(sx):
                    bit_offset = idx * bits
                    long_idx = bit_offset // 64
                    bit_shift = bit_offset % 64
                    val = 0
                    if long_idx < len(states_raw):
                        v = states_raw[long_idx] & 0xFFFFFFFFFFFFFFFF
                        val = (v >> bit_shift) & mask
                        if bit_shift + bits > 64 and long_idx + 1 < len(states_raw):
                            v2 = states_raw[long_idx + 1] & 0xFFFFFFFFFFFFFFFF
                            val |= (v2 << (64 - bit_shift)) & mask
                    idx += 1
                    if val >= psize:
                        continue
                    entry = palette_raw[val]
                    name = entry.get('Name', '') if isinstance(entry, dict) else ''
                    if not name or name == 'minecraft:air':
                        continue
                    #   Properties [facing=east,half=bottom]
                    if isinstance(entry, dict):
                        props = entry.get('Properties')
                        if props:
                            state_str = ','.join(f'{k}={v}' for k, v in props.items())
                            name = f'{name}[{state_str}]'
                    wx = rx + bx
                    wy = ry + by
                    wz = rz + bz
                    blocks.append({'x': wx, 'y': wy, 'z': wz, 'id': name})
                    min_x = min(min_x, wx); max_x = max(max_x, wx)
                    min_y = min(min_y, wy); max_y = max(max_y, wy)
                    min_z = min(min_z, wz); max_z = max(max_z, wz)
    if not blocks:
        raise ValueError("未找到任何方块")
    bw = max_x - min_x + 1
    bh = max_y - min_y + 1
    bl = max_z - min_z + 1
    for b in blocks:
        b['x'] -= min_x
        b['y'] -= min_y
        b['z'] -= min_z
    print(f"   方块数: {len(blocks):,}, 尺寸: {bw}x{bh}x{bl}", flush=True)
    return blocks, bw, bh, bl

# ==== lines 932-991 ====
def parse_txt_commands(file_path):
    """ .txt  setblock/fill ,  (, , , )

    :
      setblock x y z block_name
      fill x1 y1 z1 x2 y2 z2 block_name
      # 
    """
    blocks = []
    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if not parts:
                continue
            cmd = parts[0].lower()
            try:
                if cmd == 'setblock' and len(parts) >= 5:
                    x, y, z = int(parts[1]), int(parts[2]), int(parts[3])
                    bid = parts[4]
                    blocks.append({'x': x, 'y': y, 'z': z, 'id': bid})
                    min_x, max_x = min(min_x, x), max(max_x, x)
                    min_y, max_y = min(min_y, y), max(max_y, y)
                    min_z, max_z = min(min_z, z), max(max_z, z)
                elif cmd == 'fill' and len(parts) >= 7:
                    x1, y1, z1 = int(parts[1]), int(parts[2]), int(parts[3])
                    x2, y2, z2 = int(parts[4]), int(parts[5]), int(parts[6])
                    bid = parts[7]
                    for x in range(min(x1, x2), max(x1, x2) + 1):
                        for y in range(min(y1, y2), max(y1, y2) + 1):
                            for z in range(min(z1, z2), max(z1, z2) + 1):
                                blocks.append({'x': x, 'y': y, 'z': z, 'id': bid})
                    min_x = min(min_x, x1, x2); max_x = max(max_x, x1, x2)
                    min_y = min(min_y, y1, y2); max_y = max(max_y, y1, y2)
                    min_z = min(min_z, z1, z2); max_z = max(max_z, z1, z2)
            except (ValueError, IndexError):
                continue

    if not blocks:
        print("  setblock/fill ")
        return [], 0, 0, 0

    width = max_x - min_x + 1
    height = max_y - min_y + 1
    length = max_z - min_z + 1

    #  0 
    for b in blocks:
        b['x'] -= min_x
        b['y'] -= min_y
        b['z'] -= min_z

    print(f" : {width} × {height} × {length}")
    print(f" : {len(blocks)} ")
    return blocks, width, height, length

# ==== lines 998-1006 ====
def parse_building(file_path):
    """"""
    ext = Path(file_path).suffix.lower()
    if ext == '.txt':
        return parse_txt_commands(file_path)
    elif ext == '.litematic':
        return parse_litematic(file_path)
    else:
        return parse_schematic(file_path)

# ==== lines 1013-1767 ====
BEDROCK_ID_MAP = {
    # 
    "minecraft:stone": "stone",
    "minecraft:granite": "granite",
    "minecraft:polished_granite": "granite 1",
    "minecraft:diorite": "diorite",
    "minecraft:polished_diorite": "diorite 1",
    "minecraft:andesite": "andesite",
    "minecraft:polished_andesite": "andesite 1",
    "minecraft:cobblestone": "cobblestone",
    "minecraft:bedrock": "bedrock",
    "minecraft:deepslate": "deepslate",
    "minecraft:cobbled_deepslate": "cobbled_deepslate",
    "minecraft:tuff": "tuff",
    "minecraft:calcite": "calcite",
    "minecraft:dripstone_block": "dripstone_block",
    
    # 
    "minecraft:dirt": "dirt",
    "minecraft:grass_block": "grass",
    "minecraft:coarse_dirt": "dirt 1",
    "minecraft:podzol": "podzol",
    "minecraft:mycelium": "mycelium",
    "minecraft:moss_block": "moss_block",
    
    # 
    "minecraft:sand": "sand",
    "minecraft:red_sand": "sand 1",
    "minecraft:gravel": "gravel",
    "minecraft:clay": "clay",
    
    # 
    "minecraft:coal_ore": "coal_ore",
    "minecraft:deepslate_coal_ore": "deepslate_coal_ore",
    "minecraft:iron_ore": "iron_ore",
    "minecraft:deepslate_iron_ore": "deepslate_iron_ore",
    "minecraft:gold_ore": "gold_ore",
    "minecraft:deepslate_gold_ore": "deepslate_gold_ore",
    "minecraft:copper_ore": "copper_ore",
    "minecraft:deepslate_copper_ore": "deepslate_copper_ore",
    "minecraft:redstone_ore": "redstone_ore",
    "minecraft:deepslate_redstone_ore": "deepslate_redstone_ore",
    "minecraft:emerald_ore": "emerald_ore",
    "minecraft:deepslate_emerald_ore": "deepslate_emerald_ore",
    "minecraft:lapis_ore": "lapis_ore",
    "minecraft:deepslate_lapis_ore": "deepslate_lapis_ore",
    "minecraft:diamond_ore": "diamond_ore",
    "minecraft:deepslate_diamond_ore": "deepslate_diamond_ore",
    "minecraft:nether_quartz_ore": "quartz_ore",
    "minecraft:nether_gold_ore": "nether_gold_ore",
    
    # 
    "minecraft:oak_log": "oak_log",
    "minecraft:spruce_log": "spruce_log",
    "minecraft:birch_log": "birch_log",
    "minecraft:jungle_log": "jungle_log",
    "minecraft:acacia_log": "acacia_log",
    "minecraft:dark_oak_log": "dark_oak_log",
    "minecraft:mangrove_log": "mangrove_log",
    "minecraft:cherry_log": "cherry_log",
    "minecraft:crimson_stem": "crimson_stem",
    "minecraft:warped_stem": "warped_stem",
    "minecraft:stripped_oak_log": "stripped_oak_log",
    "minecraft:stripped_spruce_log": "stripped_spruce_log",
    "minecraft:stripped_birch_log": "stripped_birch_log",
    "minecraft:stripped_jungle_log": "stripped_jungle_log",
    "minecraft:stripped_acacia_log": "stripped_acacia_log",
    "minecraft:stripped_dark_oak_log": "stripped_dark_oak_log",
    "minecraft:stripped_mangrove_log": "stripped_mangrove_log",
    "minecraft:stripped_cherry_log": "stripped_cherry_log",
    "minecraft:stripped_crimson_stem": "stripped_crimson_stem",
    "minecraft:stripped_warped_stem": "stripped_warped_stem",
    
    # 
    "minecraft:oak_planks": "planks",
    "minecraft:spruce_planks": "planks 1",
    "minecraft:birch_planks": "planks 2",
    "minecraft:jungle_planks": "planks 3",
    "minecraft:acacia_planks": "planks 4",
    "minecraft:dark_oak_planks": "planks 5",
    "minecraft:mangrove_planks": "planks 6",
    "minecraft:cherry_planks": "planks 7",
    "minecraft:crimson_planks": "crimson_planks",
    "minecraft:warped_planks": "warped_planks",
    
    # 
    "minecraft:oak_leaves": "oak_leaves",
    "minecraft:spruce_leaves": "spruce_leaves",
    "minecraft:birch_leaves": "birch_leaves",
    "minecraft:jungle_leaves": "jungle_leaves",
    "minecraft:acacia_leaves": "acacia_leaves",
    "minecraft:dark_oak_leaves": "dark_oak_leaves",
    "minecraft:mangrove_leaves": "mangrove_leaves",
    "minecraft:cherry_leaves": "cherry_leaves",
    
    # 
    "minecraft:stone_bricks": "stone_bricks",
    "minecraft:mossy_stone_bricks": "mossy_stone_bricks",
    "minecraft:cracked_stone_bricks": "cracked_stone_bricks",
    "minecraft:chiseled_stone_bricks": "chiseled_stone_bricks",
    "minecraft:bricks": "brick_block",
    "minecraft:nether_bricks": "nether_brick",
    "minecraft:red_nether_bricks": "red_nether_brick",
    "minecraft:end_stone_bricks": "end_stone_bricks",
    
    # 
    "minecraft:glass": "glass",
    "minecraft:glass_pane": "glass_pane",
    "minecraft:white_stained_glass": "white_stained_glass",
    "minecraft:orange_stained_glass": "orange_stained_glass",
    "minecraft:magenta_stained_glass": "magenta_stained_glass",
    "minecraft:light_blue_stained_glass": "light_blue_stained_glass",
    "minecraft:yellow_stained_glass": "yellow_stained_glass",
    "minecraft:lime_stained_glass": "lime_stained_glass",
    "minecraft:pink_stained_glass": "pink_stained_glass",
    "minecraft:gray_stained_glass": "gray_stained_glass",
    "minecraft:light_gray_stained_glass": "light_gray_stained_glass",
    "minecraft:cyan_stained_glass": "cyan_stained_glass",
    "minecraft:purple_stained_glass": "purple_stained_glass",
    "minecraft:blue_stained_glass": "blue_stained_glass",
    "minecraft:brown_stained_glass": "brown_stained_glass",
    "minecraft:green_stained_glass": "green_stained_glass",
    "minecraft:red_stained_glass": "red_stained_glass",
    "minecraft:black_stained_glass": "black_stained_glass",
    
    # 
    "minecraft:white_wool": "wool",
    "minecraft:orange_wool": "wool 1",
    "minecraft:magenta_wool": "wool 2",
    "minecraft:light_blue_wool": "wool 3",
    "minecraft:yellow_wool": "wool 4",
    "minecraft:lime_wool": "wool 5",
    "minecraft:pink_wool": "wool 6",
    "minecraft:gray_wool": "wool 7",
    "minecraft:light_gray_wool": "wool 8",
    "minecraft:cyan_wool": "wool 9",
    "minecraft:purple_wool": "wool 10",
    "minecraft:blue_wool": "wool 11",
    "minecraft:brown_wool": "wool 12",
    "minecraft:green_wool": "wool 13",
    "minecraft:red_wool": "wool 14",
    "minecraft:black_wool": "wool 15",
    
    # 
    "minecraft:coal_block": "coal_block",
    "minecraft:iron_block": "iron_block",
    "minecraft:gold_block": "gold_block",
    "minecraft:diamond_block": "diamond_block",
    "minecraft:emerald_block": "emerald_block",
    "minecraft:redstone_block": "redstone_block",
    "minecraft:lapis_block": "lapis_block",
    "minecraft:copper_block": "copper_block",
    "minecraft:exposed_copper": "exposed_copper",
    "minecraft:weathered_copper": "weathered_copper",
    "minecraft:oxidized_copper": "oxidized_copper",
    "minecraft:cut_copper": "cut_copper",
    "minecraft:exposed_cut_copper": "exposed_cut_copper",
    "minecraft:weathered_cut_copper": "weathered_cut_copper",
    "minecraft:oxidized_cut_copper": "oxidized_cut_copper",
    
    # 
    "minecraft:netherrack": "netherrack",
    "minecraft:soul_sand": "soul_sand",
    "minecraft:soul_soil": "soul_soil",
    "minecraft:basalt": "basalt",
    "minecraft:polished_basalt": "polished_basalt",
    "minecraft:blackstone": "blackstone",
    "minecraft:gilded_blackstone": "gilded_blackstone",
    "minecraft:polished_blackstone": "polished_blackstone",
    "minecraft:polished_blackstone_bricks": "polished_blackstone_bricks",
    "minecraft:cracked_polished_blackstone_bricks": "cracked_polished_blackstone_bricks",
    "minecraft:chiseled_polished_blackstone": "chiseled_polished_blackstone",
    "minecraft:magma_block": "magma",
    "minecraft:glowstone": "glowstone",
    "minecraft:shroomlight": "shroomlight",
    
    # 
    "minecraft:end_stone": "end_stone",
    "minecraft:purpur_block": "purpur_block",
    "minecraft:purpur_pillar": "purpur_pillar",
    "minecraft:purpur_stairs": "purpur_stairs",
    "minecraft:purpur_slab": "purpur_slab",
    
    # 
    "minecraft:water": "water",
    "minecraft:lava": "lava",
    "minecraft:ice": "ice",
    "minecraft:packed_ice": "packed_ice",
    "minecraft:blue_ice": "blue_ice",
    "minecraft:snow": "snow",
    "minecraft:snow_block": "snow_layer",
    "minecraft:obsidian": "obsidian",
    "minecraft:crying_obsidian": "crying_obsidian",
    "minecraft:sponge": "sponge",
    "minecraft:wet_sponge": "sponge 1",
    "minecraft:slime_block": "slime",
    "minecraft:honey_block": "honey_block",
    "minecraft:bone_block": "bone_block",
    "minecraft:quartz_block": "quartz_block",
    "minecraft:quartz_pillar": "quartz_pillar",
    "minecraft:chiseled_quartz": "chiseled_quartz_block",
    "minecraft:terracotta": "terracotta",
    "minecraft:white_terracotta": "terracotta 0",
    "minecraft:orange_terracotta": "terracotta 1",
    "minecraft:magenta_terracotta": "terracotta 2",
    "minecraft:light_blue_terracotta": "terracotta 3",
    "minecraft:yellow_terracotta": "terracotta 4",
    "minecraft:lime_terracotta": "terracotta 5",
    "minecraft:pink_terracotta": "terracotta 6",
    "minecraft:gray_terracotta": "terracotta 7",
    "minecraft:light_gray_terracotta": "terracotta 8",
    "minecraft:cyan_terracotta": "terracotta 9",
    "minecraft:purple_terracotta": "terracotta 10",
    "minecraft:blue_terracotta": "terracotta 11",
    "minecraft:brown_terracotta": "terracotta 12",
    "minecraft:green_terracotta": "terracotta 13",
    "minecraft:red_terracotta": "terracotta 14",
    "minecraft:black_terracotta": "terracotta 15",
    "minecraft:concrete": "concrete",
    "minecraft:white_concrete": "concrete 0",
    "minecraft:orange_concrete": "concrete 1",
    "minecraft:magenta_concrete": "concrete 2",
    "minecraft:light_blue_concrete": "concrete 3",
    "minecraft:yellow_concrete": "concrete 4",
    "minecraft:lime_concrete": "concrete 5",
    "minecraft:pink_concrete": "concrete 6",
    "minecraft:gray_concrete": "concrete 7",
    "minecraft:light_gray_concrete": "concrete 8",
    "minecraft:cyan_concrete": "concrete 9",
    "minecraft:purple_concrete": "concrete 10",
    "minecraft:blue_concrete": "concrete 11",
    "minecraft:brown_concrete": "concrete 12",
    "minecraft:green_concrete": "concrete 13",
    "minecraft:red_concrete": "concrete 14",
    "minecraft:black_concrete": "concrete 15",

    # ==========  ==========
    "minecraft:oak_stairs": "oak_stairs",
    "minecraft:spruce_stairs": "spruce_stairs",
    "minecraft:birch_stairs": "birch_stairs",
    "minecraft:jungle_stairs": "jungle_stairs",
    "minecraft:acacia_stairs": "acacia_stairs",
    "minecraft:dark_oak_stairs": "dark_oak_stairs",
    "minecraft:mangrove_stairs": "mangrove_stairs",
    "minecraft:cherry_stairs": "cherry_stairs",
    "minecraft:bamboo_stairs": "bamboo_stairs",
    "minecraft:crimson_stairs": "crimson_stairs",
    "minecraft:warped_stairs": "warped_stairs",
    "minecraft:stone_stairs": "stone_stairs",
    "minecraft:cobblestone_stairs": "cobblestone_stairs",
    "minecraft:mossy_cobblestone_stairs": "mossy_cobblestone_stairs",
    "minecraft:stone_brick_stairs": "stone_brick_stairs",
    "minecraft:mossy_stone_brick_stairs": "mossy_stone_brick_stairs",
    "minecraft:andesite_stairs": "andesite_stairs",
    "minecraft:polished_andesite_stairs": "polished_andesite_stairs",
    "minecraft:diorite_stairs": "diorite_stairs",
    "minecraft:polished_diorite_stairs": "polished_diorite_stairs",
    "minecraft:granite_stairs": "granite_stairs",
    "minecraft:polished_granite_stairs": "polished_granite_stairs",
    "minecraft:sandstone_stairs": "sandstone_stairs",
    "minecraft:smooth_sandstone_stairs": "smooth_sandstone_stairs",
    "minecraft:red_sandstone_stairs": "red_sandstone_stairs",
    "minecraft:smooth_red_sandstone_stairs": "smooth_red_sandstone_stairs",
    "minecraft:brick_stairs": "brick_stairs",
    "minecraft:mud_brick_stairs": "mud_brick_stairs",
    "minecraft:nether_brick_stairs": "nether_brick_stairs",
    "minecraft:red_nether_brick_stairs": "red_nether_brick_stairs",
    "minecraft:quartz_stairs": "quartz_stairs",
    "minecraft:smooth_quartz_stairs": "smooth_quartz_stairs",
    "minecraft:purpur_stairs": "purpur_stairs",
    "minecraft:prismarine_stairs": "prismarine_stairs",
    "minecraft:prismarine_brick_stairs": "prismarine_brick_stairs",
    "minecraft:dark_prismarine_stairs": "dark_prismarine_stairs",
    "minecraft:blackstone_stairs": "blackstone_stairs",
    "minecraft:polished_blackstone_stairs": "polished_blackstone_stairs",
    "minecraft:polished_blackstone_brick_stairs": "polished_blackstone_brick_stairs",
    "minecraft:end_stone_brick_stairs": "end_stone_brick_stairs",
    "minecraft:deepslate_tile_stairs": "deepslate_tile_stairs",
    "minecraft:deepslate_brick_stairs": "deepslate_brick_stairs",
    "minecraft:cobbled_deepslate_stairs": "cobbled_deepslate_stairs",
    "minecraft:polished_deepslate_stairs": "polished_deepslate_stairs",
    "minecraft:cut_copper_stairs": "cut_copper_stairs",
    "minecraft:exposed_cut_copper_stairs": "exposed_cut_copper_stairs",
    "minecraft:weathered_cut_copper_stairs": "weathered_cut_copper_stairs",
    "minecraft:oxidized_cut_copper_stairs": "oxidized_cut_copper_stairs",
    "minecraft:waxed_cut_copper_stairs": "waxed_cut_copper_stairs",
    "minecraft:waxed_exposed_cut_copper_stairs": "waxed_exposed_cut_copper_stairs",
    "minecraft:waxed_weathered_cut_copper_stairs": "waxed_weathered_cut_copper_stairs",
    "minecraft:waxed_oxidized_cut_copper_stairs": "waxed_oxidized_cut_copper_stairs",

    # ==========  ==========
    "minecraft:oak_slab": "oak_slab",
    "minecraft:spruce_slab": "spruce_slab",
    "minecraft:birch_slab": "birch_slab",
    "minecraft:jungle_slab": "jungle_slab",
    "minecraft:acacia_slab": "acacia_slab",
    "minecraft:dark_oak_slab": "dark_oak_slab",
    "minecraft:mangrove_slab": "mangrove_slab",
    "minecraft:cherry_slab": "cherry_slab",
    "minecraft:bamboo_slab": "bamboo_slab",
    "minecraft:crimson_slab": "crimson_slab",
    "minecraft:warped_slab": "warped_slab",
    "minecraft:stone_slab": "stone_slab",
    "minecraft:cobblestone_slab": "cobblestone_slab",
    "minecraft:mossy_cobblestone_slab": "mossy_cobblestone_slab",
    "minecraft:stone_brick_slab": "stone_brick_slab",
    "minecraft:mossy_stone_brick_slab": "mossy_stone_brick_slab",
    "minecraft:andesite_slab": "andesite_slab",
    "minecraft:polished_andesite_slab": "polished_andesite_slab",
    "minecraft:diorite_slab": "diorite_slab",
    "minecraft:polished_diorite_slab": "polished_diorite_slab",
    "minecraft:granite_slab": "granite_slab",
    "minecraft:polished_granite_slab": "polished_granite_slab",
    "minecraft:sandstone_slab": "sandstone_slab",
    "minecraft:cut_sandstone_slab": "cut_sandstone_slab",
    "minecraft:smooth_sandstone_slab": "smooth_sandstone_slab",
    "minecraft:red_sandstone_slab": "red_sandstone_slab",
    "minecraft:cut_red_sandstone_slab": "cut_red_sandstone_slab",
    "minecraft:smooth_red_sandstone_slab": "smooth_red_sandstone_slab",
    "minecraft:brick_slab": "brick_slab",
    "minecraft:mud_brick_slab": "mud_brick_slab",
    "minecraft:nether_brick_slab": "nether_brick_slab",
    "minecraft:red_nether_brick_slab": "red_nether_brick_slab",
    "minecraft:quartz_slab": "quartz_slab",
    "minecraft:smooth_quartz_slab": "smooth_quartz_slab",
    "minecraft:purpur_slab": "purpur_slab",
    "minecraft:prismarine_slab": "prismarine_slab",
    "minecraft:prismarine_brick_slab": "prismarine_brick_slab",
    "minecraft:dark_prismarine_slab": "dark_prismarine_slab",
    "minecraft:blackstone_slab": "blackstone_slab",
    "minecraft:polished_blackstone_slab": "polished_blackstone_slab",
    "minecraft:polished_blackstone_brick_slab": "polished_blackstone_brick_slab",
    "minecraft:end_stone_brick_slab": "end_stone_brick_slab",
    "minecraft:deepslate_tile_slab": "deepslate_tile_slab",
    "minecraft:deepslate_brick_slab": "deepslate_brick_slab",
    "minecraft:cobbled_deepslate_slab": "cobbled_deepslate_slab",
    "minecraft:polished_deepslate_slab": "polished_deepslate_slab",
    "minecraft:cut_copper_slab": "cut_copper_slab",
    "minecraft:exposed_cut_copper_slab": "exposed_cut_copper_slab",
    "minecraft:weathered_cut_copper_slab": "weathered_cut_copper_slab",
    "minecraft:oxidized_cut_copper_slab": "oxidized_cut_copper_slab",
    "minecraft:waxed_cut_copper_slab": "waxed_cut_copper_slab",
    "minecraft:waxed_exposed_cut_copper_slab": "waxed_exposed_cut_copper_slab",
    "minecraft:waxed_weathered_cut_copper_slab": "waxed_weathered_cut_copper_slab",
    "minecraft:waxed_oxidized_cut_copper_slab": "waxed_oxidized_cut_copper_slab",

    # ==========  &  ==========
    "minecraft:oak_fence": "oak_fence",
    "minecraft:spruce_fence": "spruce_fence",
    "minecraft:birch_fence": "birch_fence",
    "minecraft:jungle_fence": "jungle_fence",
    "minecraft:acacia_fence": "acacia_fence",
    "minecraft:dark_oak_fence": "dark_oak_fence",
    "minecraft:mangrove_fence": "mangrove_fence",
    "minecraft:cherry_fence": "cherry_fence",
    "minecraft:bamboo_fence": "bamboo_fence",
    "minecraft:crimson_fence": "crimson_fence",
    "minecraft:warped_fence": "warped_fence",
    "minecraft:nether_brick_fence": "nether_brick_fence",
    "minecraft:oak_fence_gate": "oak_fence_gate",
    "minecraft:spruce_fence_gate": "spruce_fence_gate",
    "minecraft:birch_fence_gate": "birch_fence_gate",
    "minecraft:jungle_fence_gate": "jungle_fence_gate",
    "minecraft:acacia_fence_gate": "acacia_fence_gate",
    "minecraft:dark_oak_fence_gate": "dark_oak_fence_gate",
    "minecraft:mangrove_fence_gate": "mangrove_fence_gate",
    "minecraft:cherry_fence_gate": "cherry_fence_gate",
    "minecraft:bamboo_fence_gate": "bamboo_fence_gate",
    "minecraft:crimson_fence_gate": "crimson_fence_gate",
    "minecraft:warped_fence_gate": "warped_fence_gate",

    # ==========  ==========
    "minecraft:cobblestone_wall": "cobblestone_wall",
    "minecraft:mossy_cobblestone_wall": "mossy_cobblestone_wall",
    "minecraft:stone_brick_wall": "stone_brick_wall",
    "minecraft:mossy_stone_brick_wall": "mossy_stone_brick_wall",
    "minecraft:andesite_wall": "andesite_wall",
    "minecraft:diorite_wall": "diorite_wall",
    "minecraft:granite_wall": "granite_wall",
    "minecraft:sandstone_wall": "sandstone_wall",
    "minecraft:red_sandstone_wall": "red_sandstone_wall",
    "minecraft:brick_wall": "brick_wall",
    "minecraft:mud_brick_wall": "mud_brick_wall",
    "minecraft:nether_brick_wall": "nether_brick_wall",
    "minecraft:red_nether_brick_wall": "red_nether_brick_wall",
    "minecraft:end_stone_brick_wall": "end_stone_brick_wall",
    "minecraft:prismarine_wall": "prismarine_wall",
    "minecraft:blackstone_wall": "blackstone_wall",
    "minecraft:polished_blackstone_wall": "polished_blackstone_wall",
    "minecraft:polished_blackstone_brick_wall": "polished_blackstone_brick_wall",
    "minecraft:deepslate_tile_wall": "deepslate_tile_wall",
    "minecraft:deepslate_brick_wall": "deepslate_brick_wall",
    "minecraft:cobbled_deepslate_wall": "cobbled_deepslate_wall",
    "minecraft:polished_deepslate_wall": "polished_deepslate_wall",

    # ==========  &  ==========
    "minecraft:oak_door": "oak_door",
    "minecraft:spruce_door": "spruce_door",
    "minecraft:birch_door": "birch_door",
    "minecraft:jungle_door": "jungle_door",
    "minecraft:acacia_door": "acacia_door",
    "minecraft:dark_oak_door": "dark_oak_door",
    "minecraft:mangrove_door": "mangrove_door",
    "minecraft:cherry_door": "cherry_door",
    "minecraft:bamboo_door": "bamboo_door",
    "minecraft:crimson_door": "crimson_door",
    "minecraft:warped_door": "warped_door",
    "minecraft:iron_door": "iron_door",
    # 活板门: 由 get_bedrock_id 特殊处理 -> trapdoor["wood_type":...] (兼容全部 1.21+)
    "minecraft:oak_trapdoor": "trapdoor",
    "minecraft:spruce_trapdoor": "trapdoor",
    "minecraft:birch_trapdoor": "trapdoor",
    "minecraft:jungle_trapdoor": "trapdoor",
    "minecraft:acacia_trapdoor": "trapdoor",
    "minecraft:dark_oak_trapdoor": "trapdoor",
    "minecraft:mangrove_trapdoor": "trapdoor",
    "minecraft:cherry_trapdoor": "trapdoor",
    "minecraft:bamboo_trapdoor": "trapdoor",
    "minecraft:crimson_trapdoor": "trapdoor",
    "minecraft:warped_trapdoor": "trapdoor",
    "minecraft:iron_trapdoor": "iron_trapdoor",

    # ==========  &  ==========
    "minecraft:oak_button": "oak_button",
    "minecraft:spruce_button": "spruce_button",
    "minecraft:birch_button": "birch_button",
    "minecraft:jungle_button": "jungle_button",
    "minecraft:acacia_button": "acacia_button",
    "minecraft:dark_oak_button": "dark_oak_button",
    "minecraft:mangrove_button": "mangrove_button",
    "minecraft:cherry_button": "cherry_button",
    "minecraft:bamboo_button": "bamboo_button",
    "minecraft:crimson_button": "crimson_button",
    "minecraft:warped_button": "warped_button",
    "minecraft:stone_button": "stone_button",
    "minecraft:polished_blackstone_button": "polished_blackstone_button",
    "minecraft:oak_pressure_plate": "oak_pressure_plate",
    "minecraft:spruce_pressure_plate": "spruce_pressure_plate",
    "minecraft:birch_pressure_plate": "birch_pressure_plate",
    "minecraft:jungle_pressure_plate": "jungle_pressure_plate",
    "minecraft:acacia_pressure_plate": "acacia_pressure_plate",
    "minecraft:dark_oak_pressure_plate": "dark_oak_pressure_plate",
    "minecraft:mangrove_pressure_plate": "mangrove_pressure_plate",
    "minecraft:cherry_pressure_plate": "cherry_pressure_plate",
    "minecraft:bamboo_pressure_plate": "bamboo_pressure_plate",
    "minecraft:crimson_pressure_plate": "crimson_pressure_plate",
    "minecraft:warped_pressure_plate": "warped_pressure_plate",
    "minecraft:stone_pressure_plate": "stone_pressure_plate",
    "minecraft:polished_blackstone_pressure_plate": "polished_blackstone_pressure_plate",
    "minecraft:light_weighted_pressure_plate": "light_weighted_pressure_plate",
    "minecraft:heavy_weighted_pressure_plate": "heavy_weighted_pressure_plate",

    # ==========  ==========
    "minecraft:redstone_torch": "redstone_torch",
    "minecraft:redstone_wall_torch": "redstone_torch",
    "minecraft:redstone_lamp": "redstone_lamp",
    "minecraft:piston": "piston",
    "minecraft:sticky_piston": "sticky_piston",
    "minecraft:dispenser": "dispenser",
    "minecraft:dropper": "dropper",
    "minecraft:observer": "observer",
    "minecraft:hopper": "hopper",
    "minecraft:repeater": "repeater",
    "minecraft:comparator": "comparator",
    "minecraft:note_block": "noteblock",
    "minecraft:tnt": "tnt",
    "minecraft:lever": "lever",
    "minecraft:daylight_detector": "daylight_detector",
    "minecraft:tripwire_hook": "tripwire_hook",
    "minecraft:target": "target",
    "minecraft:sculk_sensor": "sculk_sensor",
    "minecraft:calibrated_sculk_sensor": "calibrated_sculk_sensor",

    # ==========  ==========
    "minecraft:torch": "torch",
    "minecraft:wall_torch": "torch",
    "minecraft:soul_torch": "soul_torch",
    "minecraft:soul_wall_torch": "soul_torch",
    "minecraft:lantern": "lantern",
    "minecraft:soul_lantern": "soul_lantern",
    "minecraft:sea_lantern": "sea_lantern",
    "minecraft:jack_o_lantern": "jack_o_lantern",
    "minecraft:campfire": "campfire",
    "minecraft:soul_campfire": "soul_campfire",
    "minecraft:candle": "candle",
    "minecraft:white_candle": "white_candle",
    "minecraft:end_rod": "end_rod",
    "minecraft:froglight": "verdant_froglight",
    "minecraft:pearlescent_froglight": "pearlescent_froglight",
    "minecraft:verdant_froglight": "verdant_froglight",
    "minecraft:ochre_froglight": "ochre_froglight",

    # ==========  /  ==========
    "minecraft:grass": "grass",  # 
    "minecraft:tall_grass": "tallgrass",
    "minecraft:fern": "fern",
    "minecraft:large_fern": "large_fern",
    "minecraft:dead_bush": "deadbush",
    "minecraft:dandelion": "dandelion",
    "minecraft:poppy": "poppy",
    "minecraft:blue_orchid": "blue_orchid",
    "minecraft:allium": "allium",
    "minecraft:azure_bluet": "azure_bluet",
    "minecraft:red_tulip": "red_tulip",
    "minecraft:orange_tulip": "orange_tulip",
    "minecraft:white_tulip": "white_tulip",
    "minecraft:pink_tulip": "pink_tulip",
    "minecraft:oxeye_daisy": "oxeye_daisy",
    "minecraft:cornflower": "cornflower",
    "minecraft:lily_of_the_valley": "lily_of_the_valley",
    "minecraft:wither_rose": "wither_rose",
    "minecraft:sunflower": "sunflower",
    "minecraft:lilac": "lilac",
    "minecraft:rose_bush": "rose_bush",
    "minecraft:peony": "peony",
    "minecraft:lily_pad": "waterlily",
    "minecraft:vine": "vine",
    "minecraft:weeping_vines": "weeping_vines",
    "minecraft:twisting_vines": "twisting_vines",
    "minecraft:cactus": "cactus",
    "minecraft:sugar_cane": "reeds",
    "minecraft:bamboo": "bamboo",
    "minecraft:bamboo_sapling": "bamboo_sapling",
    "minecraft:brown_mushroom": "brown_mushroom",
    "minecraft:red_mushroom": "red_mushroom",
    "minecraft:brown_mushroom_block": "brown_mushroom_block",
    "minecraft:red_mushroom_block": "red_mushroom_block",
    "minecraft:mushroom_stem": "mushroom_stem",
    "minecraft:crimson_fungus": "crimson_fungus",
    "minecraft:warped_fungus": "warped_fungus",
    "minecraft:crimson_roots": "crimson_roots",
    "minecraft:warped_roots": "warped_roots",
    "minecraft:nether_sprouts": "nether_sprouts",
    "minecraft:nether_wart": "nether_wart",
    "minecraft:nether_wart_block": "nether_wart_block",
    "minecraft:warped_wart_block": "warped_wart_block",
    "minecraft:azalea": "azalea",
    "minecraft:flowering_azalea": "flowering_azalea",
    "minecraft:azalea_leaves": "azalea_leaves",
    "minecraft:flowering_azalea_leaves": "flowering_azalea_leaves",
    "minecraft:moss_carpet": "moss_carpet",
    "minecraft:big_dripleaf": "big_dripleaf",
    "minecraft:small_dripleaf": "small_dripleaf",
    "minecraft:spore_blossom": "spore_blossom",
    "minecraft:hanging_roots": "hanging_roots",
    "minecraft:glow_lichen": "glow_lichen",
    "minecraft:pink_petals": "pink_petals",

    # ==========  ==========
    "minecraft:oak_sapling": "oak_sapling",
    "minecraft:spruce_sapling": "spruce_sapling",
    "minecraft:birch_sapling": "birch_sapling",
    "minecraft:jungle_sapling": "jungle_sapling",
    "minecraft:acacia_sapling": "acacia_sapling",
    "minecraft:dark_oak_sapling": "dark_oak_sapling",
    "minecraft:mangrove_propagule": "mangrove_propagule",
    "minecraft:cherry_sapling": "cherry_sapling",

    # ==========  /  /  ==========
    "minecraft:sandstone": "sandstone",
    "minecraft:chiseled_sandstone": "chiseled_sandstone",
    "minecraft:cut_sandstone": "cut_sandstone",
    "minecraft:smooth_sandstone": "smooth_sandstone",
    "minecraft:red_sandstone": "red_sandstone",
    "minecraft:chiseled_red_sandstone": "chiseled_red_sandstone",
    "minecraft:cut_red_sandstone": "cut_red_sandstone",
    "minecraft:smooth_red_sandstone": "smooth_red_sandstone",
    "minecraft:prismarine": "prismarine",
    "minecraft:prismarine_bricks": "prismarine_bricks",
    "minecraft:dark_prismarine": "dark_prismarine",
    "minecraft:coral_block": "coral_block",
    "minecraft:tube_coral_block": "tube_coral_block",
    "minecraft:brain_coral_block": "brain_coral_block",
    "minecraft:bubble_coral_block": "bubble_coral_block",
    "minecraft:fire_coral_block": "fire_coral_block",
    "minecraft:horn_coral_block": "horn_coral_block",
    "minecraft:tube_coral": "tube_coral",
    "minecraft:brain_coral": "brain_coral",
    "minecraft:bubble_coral": "bubble_coral",
    "minecraft:fire_coral": "fire_coral",
    "minecraft:horn_coral": "horn_coral",
    "minecraft:tube_coral_fan": "tube_coral_fan",
    "minecraft:brain_coral_fan": "brain_coral_fan",
    "minecraft:bubble_coral_fan": "bubble_coral_fan",
    "minecraft:fire_coral_fan": "fire_coral_fan",
    "minecraft:horn_coral_fan": "horn_coral_fan",
    "minecraft:dead_tube_coral_block": "dead_tube_coral_block",
    "minecraft:dead_brain_coral_block": "dead_brain_coral_block",
    "minecraft:dead_bubble_coral_block": "dead_bubble_coral_block",
    "minecraft:dead_fire_coral_block": "dead_fire_coral_block",
    "minecraft:dead_horn_coral_block": "dead_horn_coral_block",
    "minecraft:dried_kelp_block": "dried_kelp_block",

    # ==========  ==========
    "minecraft:deepslate_tiles": "deepslate_tiles",
    "minecraft:cracked_deepslate_tiles": "cracked_deepslate_tiles",
    "minecraft:deepslate_bricks": "deepslate_bricks",
    "minecraft:cracked_deepslate_bricks": "cracked_deepslate_bricks",
    "minecraft:chiseled_deepslate": "chiseled_deepslate",
    "minecraft:polished_deepslate": "polished_deepslate",
    "minecraft:reinforced_deepslate": "reinforced_deepslate",
    "minecraft:infested_deepslate": "infested_deepslate",

    # ==========  /  ==========
    "minecraft:amethyst_block": "amethyst_block",
    "minecraft:budding_amethyst": "budding_amethyst",
    "minecraft:amethyst_cluster": "amethyst_cluster",
    "minecraft:large_amethyst_bud": "large_amethyst_bud",
    "minecraft:medium_amethyst_bud": "medium_amethyst_bud",
    "minecraft:small_amethyst_bud": "small_amethyst_bud",
    "minecraft:tinted_glass": "tinted_glass",
    "minecraft:smooth_basalt": "smooth_basalt",

    # ==========  /  /  ==========
    "minecraft:mud": "mud",
    "minecraft:mud_bricks": "mud_bricks",
    "minecraft:packed_mud": "packed_mud",
    "minecraft:mangrove_roots": "mangrove_roots",
    "minecraft:muddy_mangrove_roots": "muddy_mangrove_roots",
    "minecraft:bamboo_block": "bamboo_block",
    "minecraft:stripped_bamboo_block": "stripped_bamboo_block",
    "minecraft:bamboo_planks": "bamboo_planks",
    "minecraft:bamboo_mosaic": "bamboo_mosaic",
    "minecraft:bamboo_mosaic_stairs": "bamboo_mosaic_stairs",
    "minecraft:bamboo_mosaic_slab": "bamboo_mosaic_slab",
    "minecraft:bamboo_wall_sign": "bamboo_wall_sign",

    # ==========  ==========
    "minecraft:bookshelf": "bookshelf",
    "minecraft:brick_block": "brick_block",
    "minecraft:crafting_table": "crafting_table",
    "minecraft:furnace": "furnace",
    "minecraft:blast_furnace": "blast_furnace",
    "minecraft:smoker": "smoker",
    "minecraft:barrel": "barrel",
    "minecraft:chest": "chest",
    "minecraft:trapped_chest": "trapped_chest",
    "minecraft:ender_chest": "ender_chest",
    "minecraft:shulker_box": "shulker_box",
    "minecraft:white_shulker_box": "white_shulker_box",
    "minecraft:enchanting_table": "enchanting_table",
    "minecraft:anvil": "anvil",
    "minecraft:chipped_anvil": "chipped_anvil",
    "minecraft:damaged_anvil": "damaged_anvil",
    "minecraft:jukebox": "jukebox",
    "minecraft:lodestone": "lodestone",
    "minecraft:respawn_anchor": "respawn_anchor",
    "minecraft:beacon": "beacon",
    "minecraft:conduit": "conduit",
    "minecraft:scaffolding": "scaffolding",
    "minecraft:ladder": "ladder",
    "minecraft:pointed_dripstone": "pointed_dripstone",
    "minecraft:chain": "chain",
    "minecraft:iron_bars": "iron_bars",
    "minecraft:lightning_rod": "lightning_rod",
    "minecraft:bell": "bell",
    "minecraft:grindstone": "grindstone",
    "minecraft:stonecutter": "stonecutter",
    "minecraft:loom": "loom",
    "minecraft:cartography_table": "cartography_table",
    "minecraft:fletching_table": "fletching_table",
    "minecraft:smithing_table": "smithing_table",
    "minecraft:cauldron": "cauldron",
    "minecraft:composter": "composter",
    "minecraft:beehive": "beehive",
    "minecraft:bee_nest": "bee_nest",
    "minecraft:hay_block": "hay_block",
    "minecraft:melon": "melon_block",
    "minecraft:pumpkin": "pumpkin",
    "minecraft:carved_pumpkin": "carved_pumpkin",
    "minecraft:raw_iron_block": "raw_iron_block",
    "minecraft:raw_copper_block": "raw_copper_block",
    "minecraft:raw_gold_block": "raw_gold_block",
    "minecraft:netherite_block": "netherite_block",
    "minecraft:ancient_debris": "ancient_debris",

    # ==========  /  ==========
    "minecraft:white_carpet": "white_carpet",
    "minecraft:orange_carpet": "orange_carpet",
    "minecraft:magenta_carpet": "magenta_carpet",
    "minecraft:light_blue_carpet": "light_blue_carpet",
    "minecraft:yellow_carpet": "yellow_carpet",
    "minecraft:lime_carpet": "lime_carpet",
    "minecraft:pink_carpet": "pink_carpet",
    "minecraft:gray_carpet": "gray_carpet",
    "minecraft:light_gray_carpet": "light_gray_carpet",
    "minecraft:cyan_carpet": "cyan_carpet",
    "minecraft:purple_carpet": "purple_carpet",
    "minecraft:blue_carpet": "blue_carpet",
    "minecraft:brown_carpet": "brown_carpet",
    "minecraft:green_carpet": "green_carpet",
    "minecraft:red_carpet": "red_carpet",
    "minecraft:black_carpet": "black_carpet",
    "minecraft:white_concrete_powder": "white_concrete_powder",
    "minecraft:orange_concrete_powder": "orange_concrete_powder",
    "minecraft:magenta_concrete_powder": "magenta_concrete_powder",
    "minecraft:light_blue_concrete_powder": "light_blue_concrete_powder",
    "minecraft:yellow_concrete_powder": "yellow_concrete_powder",
    "minecraft:lime_concrete_powder": "lime_concrete_powder",
    "minecraft:pink_concrete_powder": "pink_concrete_powder",
    "minecraft:gray_concrete_powder": "gray_concrete_powder",
    "minecraft:light_gray_concrete_powder": "light_gray_concrete_powder",
    "minecraft:cyan_concrete_powder": "cyan_concrete_powder",
    "minecraft:purple_concrete_powder": "purple_concrete_powder",
    "minecraft:blue_concrete_powder": "blue_concrete_powder",
    "minecraft:brown_concrete_powder": "brown_concrete_powder",
    "minecraft:green_concrete_powder": "green_concrete_powder",
    "minecraft:red_concrete_powder": "red_concrete_powder",
    "minecraft:black_concrete_powder": "black_concrete_powder",

    # ==========  /  ==========
    "minecraft:crimson_nylium": "crimson_nylium",
    "minecraft:warped_nylium": "warped_nylium",
    "minecraft:nether_sprouts": "nether_sprouts",
    "minecraft:crimson_hyphae": "crimson_hyphae",
    "minecraft:warped_hyphae": "warped_hyphae",
    "minecraft:stripped_crimson_hyphae": "stripped_crimson_hyphae",
    "minecraft:stripped_warped_hyphae": "stripped_warped_hyphae",

    # ==========  /  ==========
    "minecraft:white_glazed_terracotta": "white_glazed_terracotta",
    "minecraft:orange_glazed_terracotta": "orange_glazed_terracotta",
    "minecraft:magenta_glazed_terracotta": "magenta_glazed_terracotta",
    "minecraft:light_blue_glazed_terracotta": "light_blue_glazed_terracotta",
    "minecraft:yellow_glazed_terracotta": "yellow_glazed_terracotta",
    "minecraft:lime_glazed_terracotta": "lime_glazed_terracotta",
    "minecraft:pink_glazed_terracotta": "pink_glazed_terracotta",
    "minecraft:gray_glazed_terracotta": "gray_glazed_terracotta",
    "minecraft:light_gray_glazed_terracotta": "light_gray_glazed_terracotta",
    "minecraft:cyan_glazed_terracotta": "cyan_glazed_terracotta",
    "minecraft:purple_glazed_terracotta": "purple_glazed_terracotta",
    "minecraft:blue_glazed_terracotta": "blue_glazed_terracotta",
    "minecraft:brown_glazed_terracotta": "brown_glazed_terracotta",
    "minecraft:green_glazed_terracotta": "green_glazed_terracotta",
    "minecraft:red_glazed_terracotta": "red_glazed_terracotta",
    "minecraft:black_glazed_terracotta": "black_glazed_terracotta",

    # ==========  ==========
    "minecraft:white_stained_glass_pane": "white_stained_glass_pane",
    "minecraft:orange_stained_glass_pane": "orange_stained_glass_pane",
    "minecraft:magenta_stained_glass_pane": "magenta_stained_glass_pane",
    "minecraft:light_blue_stained_glass_pane": "light_blue_stained_glass_pane",
    "minecraft:yellow_stained_glass_pane": "yellow_stained_glass_pane",
    "minecraft:lime_stained_glass_pane": "lime_stained_glass_pane",
    "minecraft:pink_stained_glass_pane": "pink_stained_glass_pane",
    "minecraft:gray_stained_glass_pane": "gray_stained_glass_pane",
    "minecraft:light_gray_stained_glass_pane": "light_gray_stained_glass_pane",
    "minecraft:cyan_stained_glass_pane": "cyan_stained_glass_pane",
    "minecraft:purple_stained_glass_pane": "purple_stained_glass_pane",
    "minecraft:blue_stained_glass_pane": "blue_stained_glass_pane",
    "minecraft:brown_stained_glass_pane": "brown_stained_glass_pane",
    "minecraft:green_stained_glass_pane": "green_stained_glass_pane",
    "minecraft:red_stained_glass_pane": "red_stained_glass_pane",
    "minecraft:black_stained_glass_pane": "black_stained_glass_pane",
}

# ==== lines 1774-1928 ====
LEGACY_JAVA_ALIASES = {
    "minecraft:wooden_slab": "oak_slab",
    "minecraft:tallgrass": "tallgrass",
    "minecraft:reeds": "reeds",
    "minecraft:snow_layer": "snow_layer",
    "minecraft:wall_sign": "wall_sign",
    "minecraft:standing_sign": "standing_sign",
    "minecraft:bed": "bed",
    "minecraft:monster_egg": "monster_egg",
    "minecraft:red_flower": "poppy",
    "minecraft:activator_rail": "activator_rail",
    "minecraft:detector_rail": "detector_rail",
    "minecraft:rail": "rail",
    "minecraft:waterlily": "waterlily",
    "minecraft:web": "web",
    "minecraft:wooden_button": "wooden_button",
    "minecraft:melon_block": "melon_block",
    "minecraft:skull": "skull",
    "minecraft:brewing_stand": "brewing_stand",
    "minecraft:redstone_wire": "redstone_wire",
    "minecraft:mossy_cobblestone": "mossy_cobblestone",
    "minecraft:nether_brick": "nether_brick",
    "minecraft:red_nether_brick": "red_nether_brick",
    "minecraft:hardened_clay": "hardened_clay",
    "minecraft:portal": "portal",
    "minecraft:double_plant": "double_plant",
    "minecraft:tripwire": "tripwire",
    "minecraft:flower_pot": "flower_pot",
    "minecraft:end_portal_frame": "end_portal_frame",
    "minecraft:end_portal": "end_portal",
    "minecraft:structure_block": "structure_block",
    "minecraft:structure_void": "structure_void",
    "minecraft:lit_redstone_lamp": "redstone_lamp",
    "minecraft:barrier": "barrier",
    "minecraft:powered_repeater": "repeater",
    "minecraft:unlit_redstone_torch": "redstone_torch",
    "minecraft:command_block": "command_block",
    "minecraft:weighted_pressure_plate_heavy": "weighted_pressure_plate_heavy",
    "minecraft:weighted_pressure_plate_light": "weighted_pressure_plate_light",
    "minecraft:light_gray_shulker_box": "light_gray_shulker_box",
    "minecraft:carrot": "carrot",
    "minecraft:potato": "potato",
    "minecraft:cake": "cake",
    "minecraft:grass_path": "grass_path",
    "minecraft:deadbush": "deadbush",
    "minecraft:wooden_pressure_plate": "wooden_pressure_plate",
    "minecraft:stone_pressure_plate": "stone_pressure_plate",
    "minecraft:light_weighted_pressure_plate": "light_weighted_pressure_plate",
    "minecraft:heavy_weighted_pressure_plate": "heavy_weighted_pressure_plate",

    # 
    "minecraft:wooden_door": "wooden_door",
    "minecraft:iron_door": "iron_door",
    "minecraft:oak_door": "oak_door",
    "minecraft:spruce_door": "spruce_door",
    "minecraft:birch_door": "birch_door",
    "minecraft:jungle_door": "jungle_door",
    "minecraft:acacia_door": "acacia_door",
    "minecraft:dark_oak_door": "dark_oak_door",
    "minecraft:mangrove_door": "mangrove_door",
    "minecraft:cherry_door": "cherry_door",
    "minecraft:crimson_door": "crimson_door",
    "minecraft:warped_door": "warped_door",

    # 
    "minecraft:oak_fence": "oak_fence",
    "minecraft:spruce_fence": "spruce_fence",
    "minecraft:birch_fence": "birch_fence",
    "minecraft:jungle_fence": "jungle_fence",
    "minecraft:acacia_fence": "acacia_fence",
    "minecraft:dark_oak_fence": "dark_oak_fence",
    "minecraft:mangrove_fence": "mangrove_fence",
    "minecraft:cherry_fence": "cherry_fence",
    "minecraft:nether_brick_fence": "nether_brick_fence",
    "minecraft:crimson_fence": "crimson_fence",
    "minecraft:warped_fence": "warped_fence",

    # 
    "minecraft:oak_fence_gate": "oak_fence_gate",
    "minecraft:spruce_fence_gate": "spruce_fence_gate",
    "minecraft:birch_fence_gate": "birch_fence_gate",
    "minecraft:jungle_fence_gate": "jungle_fence_gate",
    "minecraft:acacia_fence_gate": "acacia_fence_gate",
    "minecraft:dark_oak_fence_gate": "dark_oak_fence_gate",
    "minecraft:mangrove_fence_gate": "mangrove_fence_gate",
    "minecraft:crimson_fence_gate": "crimson_fence_gate",
    "minecraft:warped_fence_gate": "warped_fence_gate",

    # 
    # 活板门: 由 get_bedrock_id 特殊处理 -> trapdoor["wood_type":...] (兼容全部 1.21+)
    "minecraft:oak_trapdoor": "trapdoor",
    "minecraft:spruce_trapdoor": "trapdoor",
    "minecraft:birch_trapdoor": "trapdoor",
    "minecraft:jungle_trapdoor": "trapdoor",
    "minecraft:acacia_trapdoor": "trapdoor",
    "minecraft:dark_oak_trapdoor": "trapdoor",
    "minecraft:mangrove_trapdoor": "trapdoor",
    "minecraft:iron_trapdoor": "iron_trapdoor",
    "minecraft:crimson_trapdoor": "trapdoor",
    "minecraft:warped_trapdoor": "trapdoor",

    # 
    "minecraft:birch_button": "birch_button",
    "minecraft:jungle_button": "jungle_button",
    "minecraft:acacia_button": "acacia_button",
    "minecraft:dark_oak_button": "dark_oak_button",
    "minecraft:mangrove_button": "mangrove_button",
    "minecraft:cherry_button": "cherry_button",
    "minecraft:crimson_button": "crimson_button",
    "minecraft:warped_button": "warped_button",
    "minecraft:polished_blackstone_button": "polished_blackstone_button",

    # 
    "minecraft:powered_rail": "powered_rail",

    # 
    "minecraft:crafting_table": "crafting_table",
    "minecraft:enchanting_table": "enchanting_table",
    "minecraft:furnace": "furnace",
    "minecraft:lit_furnace": "furnace",
    "minecraft:blast_furnace": "blast_furnace",
    "minecraft:smoker": "smoker",
    "minecraft:anvil": "anvil",
    "minecraft:chipped_anvil": "anvil",
    "minecraft:damaged_anvil": "anvil",
    "minecraft:grindstone": "grindstone",
    "minecraft:stonecutter": "stonecutter",
    "minecraft:lectern": "lectern",
    "minecraft:cartography_table": "cartography_table",
    "minecraft:fletching_table": "fletching_table",
    "minecraft:smithing_table": "smithing_table",
    "minecraft:loom": "loom",
    "minecraft:composter": "composter",
    "minecraft:barrel": "barrel",
    "minecraft:cauldron": "cauldron",
    "minecraft:brewing_stand": "brewing_stand",
    "minecraft:beacon": "beacon",
    "minecraft:conduit": "conduit",
    "minecraft:ender_chest": "ender_chest",
    "minecraft:shulker_box": "shulker_box",
    "minecraft:white_shulker_box": "white_shulker_box",
    "minecraft:orange_shulker_box": "orange_shulker_box",
    "minecraft:magenta_shulker_box": "magenta_shulker_box",
    "minecraft:yellow_shulker_box": "yellow_shulker_box",
    "minecraft:lime_shulker_box": "lime_shulker_box",
    "minecraft:pink_shulker_box": "pink_shulker_box",
    "minecraft:gray_shulker_box": "gray_shulker_box",
    "minecraft:cyan_shulker_box": "cyan_shulker_box",
    "minecraft:purple_shulker_box": "purple_shulker_box",
    "minecraft:blue_shulker_box": "blue_shulker_box",
    "minecraft:brown_shulker_box": "brown_shulker_box",
    "minecraft:green_shulker_box": "green_shulker_box",
    "minecraft:red_shulker_box": "red_shulker_box",
    "minecraft:black_shulker_box": "black_shulker_box",
}

# ==== lines 1931-1972 ====
def _add_data_state(name, bid, d):
    """将旧格式 data 值编码为方块状态，供 get_bedrock_id 保留方向"""
    if '[' in name: return name
    # 楼梯
    if bid in (53,67,108,109,114,128,134,135,136,156,163,164,180):
        fmap = {0:'east',1:'west',2:'south',3:'north'}
        h = 'top' if d & 4 else 'bottom'
        return f'{name}[facing={fmap.get(d&3,"east")},half={h}]'
    # 熔炉/发射器/投掷器
    if bid in (23,61,62,158):
        fmap = {2:'north',3:'south',4:'west',5:'east'}
        return f'{name}[facing={fmap.get(d,"north")}]'
    # 火把
    if bid == 50:
        fmap = {1:'east',2:'west',3:'south',4:'north',5:'up'}
        f = fmap.get(d,'up')
        return f'{name}[facing={f}]' if d != 5 else f'{name}[facing=up]'
    # 红石火把
    if bid in (75,76):
        fmap = {1:'east',2:'west',3:'south',4:'north',5:'up'}
        t = 'redstone_wall_torch' if d != 5 else 'redstone_torch'
        return f'minecraft:{t}[facing={fmap.get(d,"up")}]'
    # 梯子
    if bid == 65:
        fmap = {2:'north',3:'south',4:'west',5:'east'}
        return f'{name}[facing={fmap.get(d,"north")}]'
    # 原木
    if bid in (17,162):
        amap = {0:'y',4:'x',8:'z'}
        return f'{name}[axis={amap.get(d&12,"y")}]'
    # 活板门
    if bid in (96,167):
        fmap = {0:'north',1:'south',2:'west',3:'east'}
        h = 'top' if d & 4 else 'bottom'
        return f'{name}[facing={fmap.get(d&3,"north")},half={h}]'
    # 门
    if bid in (64,71,193,194,195,196,197):
        fmap = {0:'east',1:'south',2:'west',3:'north'}
        op = 'true' if d & 4 else 'false'
        hh = 'upper' if d & 8 else 'lower'
        return f'{name}[facing={fmap.get(d&3,"east")},half={hh},open={op}]'
    return name

# ==== lines 1975-1986 ====
def _parse_blockstate(java_id):
    """解析 [key=value,key2=value2] 方块状态，返回 (clean_id, states_dict)"""
    if "[" not in java_id:
        return java_id, {}
    name, raw = java_id.split("[", 1)
    raw = raw.rstrip("]")
    states = {}
    for pair in raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            states[k.strip()] = v.strip()
    return name, states

# ==== lines 1989-2049 ====
def _state_to_data(block_name, states):
    """将方块状态映射为基岩版 data 值"""
    facing = states.get("facing", "")
    half = states.get("half", "")
    axis = states.get("axis", "")
    if block_name.endswith("_stairs") or block_name == "minecraft:oak_stairs":
        f_map = {"east": 0, "west": 1, "south": 2, "north": 3}
        h_map = {"bottom": 0, "top": 4}
        return f_map.get(facing, 0) | h_map.get(half, 0)
    if block_name in ("furnace", "dispenser", "dropper", "minecraft:furnace",
                      "minecraft:dispenser", "minecraft:dropper", "minecraft:lit_furnace"):
        f_map = {"north": 2, "south": 3, "west": 4, "east": 5}
        return f_map.get(facing, 2)
    if block_name in ("torch", "wall_torch", "redstone_torch", "soul_torch",
                      "minecraft:torch", "minecraft:wall_torch",
                      "minecraft:redstone_torch", "minecraft:soul_torch",
                      "minecraft:soul_wall_torch"):
        if block_name.endswith("wall_torch") or "wall" in block_name:
            f_map = {"east": 1, "west": 2, "south": 3, "north": 4}
            return f_map.get(facing, 1)
        return 5
    if block_name in ("ladder", "minecraft:ladder"):
        f_map = {"north": 2, "south": 3, "west": 4, "east": 5}
        return f_map.get(facing, 2)
    if "log" in block_name or "wood" in block_name:
        a_map = {"y": 0, "x": 4, "z": 8}
        return a_map.get(axis, 0)
    if "trapdoor" in block_name:
        f_map = {"north": 0, "south": 1, "west": 2, "east": 3}
        h_map = {"bottom": 0, "top": 4}
        return f_map.get(facing, 0) | h_map.get(half, 0)
    if "door" in block_name:
        h_map = {"lower": 0, "upper": 8}
        f_map = {"east": 0, "south": 1, "west": 2, "north": 3}
        data = h_map.get(half, 0)
        if half == "lower":
            data |= f_map.get(facing, 0)
            if states.get("open") == "true":
                data |= 4
        return data
    if block_name in ("chest", "trapped_chest", "ender_chest",
                      "minecraft:chest", "minecraft:trapped_chest",
                      "minecraft:ender_chest"):
        f_map = {"north": 2, "south": 3, "west": 4, "east": 5}
        return f_map.get(facing, 2)
    if "bed" in block_name:
        f_map = {"south": 0, "west": 1, "north": 2, "east": 3}
        data = f_map.get(facing, 0)
        if states.get("part") == "head":
            data |= 8
        return data
    if "piston" in block_name or "sticky_piston" in block_name:
        f_map = {"down": 0, "up": 1, "north": 2, "south": 3, "west": 4, "east": 5}
        return f_map.get(facing, 1)
    if "command_block" in block_name or "chain_command_block" in block_name or "repeating_command_block" in block_name:
        f_map = {"down": 0, "up": 1, "north": 2, "south": 3, "west": 4, "east": 5}
        return f_map.get(facing, 0)
    if "hopper" in block_name:
        f_map = {"down": 0, "north": 2, "south": 3, "west": 4, "east": 5}
        return f_map.get(facing, 0)
    return None

# ==== lines 2052-2072 ====
def _bedrock_trapdoor(java_base, states):
    """活板门: 基岩版统一用 trapdoor + wood_type 状态 (兼容全部 1.21+)"""
    name = java_base.split(":")[-1]
    if name == "iron_trapdoor":
        block, wt = "iron_trapdoor", None
    else:
        wt = name[:-9] if name.endswith("_trapdoor") else "oak"
        if not wt:
            wt = "oak"  # 裸 "trapdoor" 视为橡木
        block = "trapdoor"
    f_map = {"north": 0, "south": 1, "west": 2, "east": 3}
    direction = f_map.get(states.get("facing", "north"), 0)
    upside = "true" if states.get("half") == "top" else "false"
    openb = "true" if states.get("open") == "true" else "false"
    sb = []
    if wt:
        sb.append('"wood_type":"%s"' % wt)
    sb.append('"direction":%d' % direction)
    sb.append('"upside_down_bit":%s' % upside)
    sb.append('"open_bit":%s' % openb)
    return "%s[%s]" % (block, ",".join(sb))

# ==== lines 2075-2100 ====
def get_bedrock_id(java_id):
    """Java ID -> Bedrock ID (保留 data 值以保证方向正确)"""
    raw_clean = java_id.split(":")[-1] if ":" in java_id else java_id
    base_name, states = _parse_blockstate(java_id)
    clean = base_name.split(":")[-1] if ":" in base_name else base_name
    # 活板门: 基岩版用 trapdoor + wood_type 状态 (兼容全部 1.21+)
    if "trapdoor" in clean:
        return _bedrock_trapdoor(base_name, states)
    # 先查找精确映射
    if java_id in BEDROCK_ID_MAP:
        result = BEDROCK_ID_MAP[java_id]
    elif base_name in BEDROCK_ID_MAP:
        result = BEDROCK_ID_MAP[base_name]
    elif java_id in LEGACY_JAVA_ALIASES:
        result = LEGACY_JAVA_ALIASES[java_id]
    elif base_name in LEGACY_JAVA_ALIASES:
        result = LEGACY_JAVA_ALIASES[base_name]
    else:
        # 未映射的方块：1.13+ 方块名（如 bamboo_wall_sign）基岩版直接对应，静默通过
        result = clean
    # 从方块状态关联 data 值
    if states:
        data = _state_to_data(base_name, states)
        if data is not None:
            result = f"{result.split()[0]} {data}" if result else clean
    return result

# ==== lines 2107-2210 ====
def compress_blocks(blocks, width, length):
    """ 2D fill 

    (Y) XZ 
    -  N>1:  fill_2d  ()
    -  1 :  setblock 

    : 

    Returns:
        list of dict: [{
            'y': int, 'type': 'fill_2d'|'setblock',
            'x1': int, 'z1': int, 'x2': int, 'z2': int,  # 
            'x': int, 'z': int,     # setblock 
            'block': str,           #  ID
            'java_id': str          #  Java ID
        }]
    """
    # : layer_grid[y][z][x] = bedrock_id
    layer_grids = defaultdict(lambda: defaultdict(lambda: {}))
    for b in blocks:
        bedrock_id = get_bedrock_id(b['id'])
        layer_grids[b['y']][b['z']][b['x']] = (bedrock_id, b['id'])

    compressed = []
    total_setblock = 0
    total_fill = 0
    total_covered = 0
    layer_keys = sorted(layer_grids.keys())
    total_layers = len(layer_keys)

    for idx, y in enumerate(layer_keys):
        layer = layer_grids[y]
        if (idx + 1) % max(1, total_layers // 5) == 0 or idx == 0 or idx == total_layers - 1:
            print(f"  …  {idx + 1}/{total_layers}  (y={y})", end='\r')

        #  2D 
        grid = []
        for z in range(length):
            row = []
            for x in range(width):
                row.append(layer[z].get(x, None))
            grid.append(row)

        visited = set()

        for z in range(length):
            for x in range(width):
                cell = grid[z][x]
                if cell is None or (x, z) in visited:
                    continue

                block_id, java_id = cell

                # 
                x_end = x
                while (x_end + 1 < width and grid[z][x_end + 1] is not None
                       and grid[z][x_end + 1][0] == block_id
                       and (x_end + 1, z) not in visited):
                    x_end += 1

                # 
                z_end = z
                can_expand = True
                while can_expand and z_end + 1 < length:
                    for check_x in range(x, x_end + 1):
                        cell_check = grid[z_end + 1][check_x]
                        if (cell_check is None or cell_check[0] != block_id
                                or (check_x, z_end + 1) in visited):
                            can_expand = False
                            break
                    if can_expand:
                        z_end += 1

                # 
                for vz in range(z, z_end + 1):
                    for vx in range(x, x_end + 1):
                        visited.add((vx, vz))

                # 
                rect_size = (x_end - x + 1) * (z_end - z + 1)
                if x_end > x or z_end > z:
                    compressed.append({
                        'y': y, 'type': 'fill_2d',
                        'x1': x, 'z1': z,
                        'x2': x_end, 'z2': z_end,
                        'block': block_id, 'java_id': java_id
                    })
                    total_fill += 1
                    total_covered += rect_size
                else:
                    compressed.append({
                        'y': y, 'type': 'setblock',
                        'x': x, 'z': z,
                        'block': block_id, 'java_id': java_id
                    })
                    total_setblock += 1
                    total_covered += 1

    compression_ratio = (1 - len(compressed) / len(blocks)) * 100 if blocks else 0
    print(f" 2D:")
    print(f"   setblock: {total_setblock} | fill_2d: {total_fill}")
    print(f"   : {len(compressed)} ( {len(blocks)} →  {compression_ratio:.1f}%)")
    return compressed

# ==== lines 2451-2796 ====
def generate_commands_typed(compressed_entries, file_name, width, length, reverse=False, use_unless=False, scoreboard_name="dr", speed=1, h_tag="h", b_tag="b", max_chars=10000):
    """ setblock + execute +  +  

    :
      1.  typeId ( 300 ,  glass=300, pane=301 ...)
      2.  x->z->y ()
      3.  tick :
         - :  type ,  step  type,  type 
         - unless(, cx/cz):
           * b: drtick+1, x, unless-tp+h
           * : unless entity @s[scores={dr=!}] run setblock ~ ~ ~ BLOCK
    """
    if not compressed_entries:
        print(" ")
        return None

    file_name = _sanitize_name(file_name)

    W, L = width, length
    if W <= 0 or L <= 0:
        print(" ")
        return None

    #  -> typeId ( 300 , "300~302")
    block_to_id = {}
    next_id = 300
    for e in compressed_entries:
        b = e['block']
        if b not in block_to_id:
            block_to_id[b] = next_id
            next_id += 1
    id_to_block = {v: k for k, v in block_to_id.items()}
    type_min, type_max = 300, next_id - 1

    # :  [minY, maxY] (),
    #  y±1 , 
    ys = sorted({e['y'] for e in compressed_entries})
    min_y, max_y = ys[0], ys[-1]
    if reverse:
        # :  i  y = max_y - i
        sweep_ys = list(range(max_y, min_y - 1, -1))
        layer_index = {y: (max_y - y) for y in sweep_ys}
        startY = max_y
        y_dir = -1
    else:
        # :  i  y = min_y + i
        sweep_ys = list(range(min_y, max_y + 1))
        layer_index = {y: (y - min_y) for y in sweep_ys}
        startY = min_y
        y_dir = 1
    H = len(sweep_ys)

    def idx_of(li, x, z):
        return (li * L + z) * W + x

    cmds = []
    cmds.append("#" + "=" * 60)
    cmds.append(f"# {file_name} | {len(compressed_entries)} | {W}x{H}x{L} | {scoreboard_name}")
    cmds.append("#" + "=" * 60)
    cmds.append("")

    #  ()
    type_ranges = []
    for e in compressed_entries:
        li = layer_index[e['y']]
        tid = block_to_id[e['block']]
        if e['type'] in ('fill_2d', 'fill'):
            for z in range(e['z1'], e['z2'] + 1):
                s = idx_of(li, e['x1'], z)
                en = idx_of(li, e['x2'], z)
                type_ranges.append((s, en, tid))
        else:
            s = idx_of(li, e['x'], e['z'])
            type_ranges.append((s, s, tid))

    type_ranges.sort(key=lambda r: r[0])
    merged = []
    for s, en, tid in type_ranges:
        if merged and merged[-1][2] == tid and s == merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], en, tid)
        else:
            merged.append((s, en, tid))
    print(f"  展开: {len(type_ranges)} → 合并: {len(merged)}, 压缩率 {(1-len(merged)/max(len(type_ranges),1))*100:.1f}%")

    standalone_manual = defaultdict(list)
    if use_unless:
        # ── 不 bump W/L，敏感值由逐值检测拆分为手动 setblock ──
        _W_orig, _L_orig = W, L

        def _c(cmd_str, comment):
            cmds.append(f"# {comment}")
            cmds.append(cmd_str)

        cmds.append("# [脉冲] [无条件] [红石控制] 一次性执行")
        _c(f"scoreboard objectives add {scoreboard_name} dummy", f"创建 {scoreboard_name} 计分板")
        _c("summon armor_stand ~ ~ ~", "召唤 h 高度扫描器")
        _c("tag @e[type=armor_stand,c=1,r=2.5,tag=!b] add h", "标记 h")
        _c(f"tp @e[tag=h,type=armor_stand] ~ ~{startY} ~", f"传送 h 到 y={startY}")
        _c("summon armor_stand ~ ~ ~", "召唤 b 位置扫描器")
        _c("tag @e[type=armor_stand,c=1,r=2.5,tag=!h] add b", "标记 b")
        _c(f"tp @e[tag=b,type=armor_stand] ~ ~{startY} ~", f"传送 b 到 y={startY}")
        _c(f"scoreboard players set @e[tag=h,type=armor_stand] {scoreboard_name} 0", "h 计数归零")
        _c(f"scoreboard players set @e[tag=b,type=armor_stand] {scoreboard_name} 0", "b 计数归零")
        cmds.append("")
        cmds.append(f"# [循环] [无条件] [保持开启] 速度{speed}x")
        _c(f"scoreboard players add @e[tag=h,type=armor_stand] {scoreboard_name} {speed}", f"h 计数 +{speed}")
        _c(f"scoreboard players add @e[tag=b,type=armor_stand] {scoreboard_name} {speed}", f"b 计数 +{speed}")
        cmds.append("")
        cmds.append("# [连锁] [无条件] [保持开启]")
        _ts = W * L * H
        _ls = W * L
        layer_size = _ls
        block_ranges = defaultdict(list)
        for s, en, tid in merged:
            block_ranges[tid].append((s, en))

        print(f"  unless 放置命令 ({len(block_to_id)} 种方块)")
        MAX_CMD_LEN = max_chars

        def _build_unless_cmd(block_name, rangelist):
            def _fmt(s, e):
                sv, ev = s * speed, e * speed
                return f"{scoreboard_name}=!{sv}" if sv == ev else f"{scoreboard_name}=!{sv}..{ev}"
            conds = ",".join(_fmt(s, e) for s, e in rangelist)
            return (f"execute as @e[tag=b,type=armor_stand] at @s "
                    f"unless entity @s[scores={{{conds}}}] "
                    f"run setblock ~ ~ ~ {block_name}")

        # ── 预建敏感数集合 ──
        import re as _r2
        _split_nums = set([20, 38, 40, 64, 86, 89])
        for _v in [_W_orig, _L_orig]:
            if _SF is not None and _SF.contains(str(_v)):
                _split_nums.add(_v)
        _specific_num_rx = _r2.compile(r'(?<!\d)(' + '|'.join(map(str, sorted(_split_nums))) + r')(?!\d)')
        def _is_specific_sensitive(v):
            return _SF is not None and _specific_num_rx.search(str(v)) is not None

        # ── 坐标反推 ──
        def _li_to_xyz(li):
            lz = li // (W * L)
            rem = li % (W * L)
            zz = rem // W
            xx = rem % W
            wy = sweep_ys[lz] if lz < len(sweep_ys) else (sweep_ys[0] if sweep_ys else startY) + lz
            return xx, wy, zz

        # ── 手动 setblock ──
        manual_cmds = []
        def _add_manual(block_name, xx, wy, zz):
            manual_cmds.append(f"setblock ~{xx + 1} ~{wy} ~{zz} {block_name}")

        total_placement = 0
        sf_manual_total = 0

        for tid in sorted(id_to_block.keys()):
            block = id_to_block[tid]
            ranges = block_ranges.get(tid, [])
            if not ranges:
                continue

            batch = []
            for s, en in ranges:
                cur_start = None
                for li in range(s, en + 1):
                    sv = li * speed
                    if _is_specific_sensitive(sv):
                        if cur_start is not None:
                            batch.append((cur_start, li - 1))
                            cur_start = None
                        xx, wy, zz = _li_to_xyz(li)
                        _add_manual(block, xx, wy, zz)
                        sf_manual_total += 1
                    else:
                        if cur_start is None:
                            cur_start = li
                if cur_start is not None:
                    batch.append((cur_start, en))

            # 合并连续的单一区间 (dr=!23,dr=!24 → dr=!23..24)
            if batch:
                cb = [batch[0]]
                for bs, be in batch[1:]:
                    if bs == cb[-1][1] + 1:
                        cb[-1] = (cb[-1][0], be)
                    else:
                        cb.append((bs, be))
                batch = cb

            # 跨区间合并 unless 指令
            temp = []
            for bs, be in batch:
                test = temp + [(bs, be)]
                cmd = _build_unless_cmd(block, test)
                if len(cmd) > MAX_CMD_LEN:
                    if temp:
                        _c(_build_unless_cmd(block, temp), f"放置 {block}")
                        total_placement += 1
                    temp = [(bs, be)]
                else:
                    temp.append((bs, be))
            if temp:
                _c(_build_unless_cmd(block, temp), f"放置 {block}")
                total_placement += 1

        print(f"  自动 unless 指令: {total_placement} 条")
        if sf_manual_total:
            print(f"[敏感词] {sf_manual_total} 个分值含敏感，已转为手动 setblock")
        if manual_cmds:
            cmds.append("")
            cmds.append(f"# ===== [手动执行] 以下 {len(manual_cmds)} 个方块含敏感分值，请逐条手动执行 =====")
            cmds.append("# 站在盔甲架起始位置，逐条输入以下 setblock 指令")
            for mc in manual_cmds:
                cmds.append(mc)
            cmds.append(f"# ===== [手动执行结束] =====")

        cmds.append("")
        _c("execute as @e[tag=b,type=armor_stand] at @s run tp @s ~1 ~ ~", "b 向右移动 1 格")
        layer_size = W * L
        total_rows = H * L
        _b_triggers = [m * W * speed for m in range(1, total_rows) if m % L != 0]
        _b_conds = [f"{scoreboard_name}=!{t}" for t in _b_triggers]
        _layer_skips_str = ",".join(f"{scoreboard_name}={i*layer_size*speed}" for i in range(1, H))
        MAX_CMD_LEN = max_chars
        _b_prefix = f"execute as @e[tag=b,type=armor_stand] unless entity @s"
        if _layer_skips_str:
            _b_suffix = f"unless entity @s[scores={{{_layer_skips_str}}}] at @s run tp @s ~-{W} ~ ~1"
        else:
            _b_suffix = f"at @s run tp @s ~-{W} ~ ~1"
        _batch = []
        for c in _b_conds:
            _test = _batch + [c]
            _full = f"{_b_prefix}[scores={{{','.join(_test)}}}] {_b_suffix}"
            if len(_full) > MAX_CMD_LEN and _batch:
                _bc = ",".join(_batch)
                _c(f"{_b_prefix}[scores={{{_bc}}}] {_b_suffix}", "b 行末回绕")
                _batch = [c]
            else:
                _batch.append(c)
        if _batch:
            _bc = ",".join(_batch)
            _c(f"{_b_prefix}[scores={{{_bc}}}] {_b_suffix}", "b 行末回绕")
        layer_size = W * L
        _h_conds = [f"{scoreboard_name}=!{i*layer_size*speed}" for i in range(1, H)]
        _h_combined = ",".join(_h_conds)
        def _append_h_tp(cs):
            _c(f"execute as @e[tag=h,type=armor_stand] unless entity @s[scores={{{cs}}}] at @s run tp @s ~ ~{y_dir} ~", "h 层推进")
            _c(f"execute as @e[tag=h,type=armor_stand] unless entity @s[scores={{{cs}}}] at @s run tp @e[tag=b,type=armor_stand] ~ ~ ~", "h 拉回 b")
        _ht = f"execute as @e[tag=h,type=armor_stand] unless entity @s[scores={{{_h_combined}}}] at @s run tp @s ~ ~{y_dir} ~"
        if len(_ht) > 13000:
            _batch_cs = []
            for c in _h_conds:
                _test = _batch_cs + [c]
                _t = f"execute as @e[tag=h,type=armor_stand] unless entity @s[scores={{{','.join(_test)}}}] at @s run tp @s ~ ~{y_dir} ~"
                if len(_t) > 13000:
                    _append_h_tp(",".join(_batch_cs))
                    _batch_cs = [c]
                else:
                    _batch_cs.append(c)
            if _batch_cs:
                _append_h_tp(",".join(_batch_cs))
        else:
            _append_h_tp(_h_combined)
        _c(f"execute as @e[tag=h,type=armor_stand] at @s run tp @s ~ ~ ~", "h 重复 tp 到自己(锁定原位)")
        cmds.append("")
        # 添加敏感分数区间的手动执行指令
        if standalone_manual:
            total = sum(len(v) for v in standalone_manual.values())
            cmds.append('')
            cmds.append('# ========== 手动执行说明（敏感词） ==========')
            cmds.append(f'# 以下 {total} 个方块包含敏感数值分数，已从自动循环中移除。')
            cmds.append('# 请在放置盔甲架的位置，按顺序逐条执行以下指令：')
            cmds.append('')
            for block in sorted(standalone_manual.keys()):
                for xx, yy, zz in standalone_manual[block]:
                    cmds.append(f'setblock ~{xx} ~{yy} ~{zz} {block}')
            cmds.append('')
            cmds.append('# =================================')

    else:
        cmds.append("scoreboard players set @e[tag=Builder] type 0")
        for s, en, tid in merged:
            cmds.append(
                f"execute as @e[tag=Builder,scores={{step={s}..{en}}}] "
                f"run scoreboard players set @s type {tid}"
            )
        cmds.append("")
        cmds.append("scoreboard players set @e[tag=Builder] type 0")
        for s, en, tid in merged:
            cmds.append(
                f"execute as @e[tag=Builder,scores={{step={s}..{en}}}] "
                f"run scoreboard players set @s type {tid}"
            )
        cmds.append("")

    if not use_unless:
        for tid in sorted(id_to_block.keys()):
            block = id_to_block[tid]
            cmds.append(
                f"execute as @e[tag=Builder,scores={{type={tid}..{tid}}}] "
                f"at @s run setblock ~ ~ ~ {block}"
            )
    cmds.append("")

    total_steps = W * L * H
    layer_size = W * L
    if not use_unless:
        cmds.append("scoreboard players add @e[tag=Builder] step 1")
        cmds.append("scoreboard players add @e[tag=Builder] cx 1")
        cmds.append("tp @e[tag=Builder] ~1 ~ ~")
        cmds.append(f"execute as @e[tag=Builder,scores={{cx={W}..}}] at @s run tp @s ~-{W} ~ ~1")
        cmds.append(f"execute as @e[tag=Builder,scores={{cx={W}..}}] run scoreboard players set @s cx 0")
        cmds.append(f"execute as @e[tag=Builder,scores={{cx={W}..}}] run scoreboard players add @s cz 1")
        cmds.append(f"execute as @e[tag=Builder,scores={{cz={L}..}}] at @s run tp @s ~ ~{y_dir} ~-{L}")
        cmds.append(f"execute as @e[tag=Builder,scores={{cz={L}..}}] run scoreboard players set @s cz 0")
        cmds.append(f"execute as @e[tag=Builder,scores={{cz={L}..}}] run scoreboard players add @s cy 1")
        cmds.append(f"execute as @e[tag=Builder,scores={{cy={H}..}}] run titleraw @a actionbar {{\"rawtext\":[{{\"text\":\" {file_name} \"}}]}}")
        cmds.append(f"execute as @e[tag=Builder,scores={{cy={H}..}}] run scoreboard players set @s cy 0")
    if use_unless:
        _c(f"titleraw @a actionbar {{\"rawtext\":[{{\"text\":\"> \"}},{{\"score\":{{\"name\":\"@e[tag=b,type=armor_stand,c=1]\",\"objective\":\"{scoreboard_name}\"}}}},{{\"text\":\" / {_ts}\"}}]}}", "显示进度条")
        _score_cond = f"{{{scoreboard_name}={_ts}..}}"
        _c(f"execute as @e[tag=b,type=armor_stand,scores={_score_cond}] at @s run titleraw @a actionbar {{\"rawtext\":[{{\"text\":\"文件 {file_name} 加载完成\"}}]}}", "加载完成提示")
    cmds.append("")

    if use_unless:
        cmds.append("# 重置(手动)")
        _c(f"scoreboard players set @e[tag=h,type=armor_stand] {scoreboard_name} 0", "h 计数归零")
        _c(f"scoreboard players set @e[tag=b,type=armor_stand] {scoreboard_name} 0", "b 计数归零")
        _c(f"tp @e[tag=h,type=armor_stand] ~ ~{startY} ~", f"传送 h 回 y={startY}")
        _c(f"tp @e[tag=b,type=armor_stand] ~ ~{startY} ~", f"传送 b 回 y={startY}")
        _c("kill @e[tag=h,type=armor_stand]", "移除 h")
        _c("kill @e[tag=b,type=armor_stand]", "移除 b")
    else:
        cmds.append("scoreboard players set @e[tag=Builder] step 0")
        cmds.append("scoreboard players set @e[tag=Builder] cx 0")
        cmds.append("scoreboard players set @e[tag=Builder] cz 0")
        cmds.append("scoreboard players set @e[tag=Builder] cy 0")
        cmds.append("scoreboard players set @e[tag=Builder] type 0")
        cmds.append(f"tp @e[tag=Builder] ~ ~{startY} ~")
        cmds.append("kill @e[tag=Builder]")
    cmds.append("")

    # 
    if h_tag != 'h' or b_tag != 'b':
        cmds = [c.replace('tag=h,', f'tag={h_tag},').replace('tag=b,', f'tag={b_tag},').replace('tag=!b]', f'tag=!{b_tag}]').replace('add h', f'add {h_tag}').replace('add b', f'add {b_tag}') for c in cmds]
    return cmds

# ==== Web API wrapper ====

import json
from pathlib import Path

def convert_schematic(file_bytes, file_name):
    """Convert schematic file bytes to commands. Returns dict with commands, log, stats."""
    import io, sys, os
    log_buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = log_buf
    try:
        # Save to temp path
        ext = Path(file_name).suffix.lower()
        blocks, width, height, length = parse_building(file_name)
        if not blocks:
            return {'error': 'No blocks found'}

        compressed = compress_blocks(blocks, width, length)
        cmds = generate_commands_typed(
            compressed, Path(file_name).stem, width, length,
            use_unless=True, scoreboard_name='dr', speed=1,
            h_tag='h', b_tag='b', max_chars=10000
        )
        if not cmds:
            return {'error': 'No commands generated'}

        return {
            'commands': '\n'.join(cmds),
            'log': log_buf.getvalue(),
            'blocks': len(blocks),
            'compressed': len(compressed),
            'total_cmds': len(cmds),
        }
    except Exception as e:
        import traceback
        return {'error': str(e), 'trace': traceback.format_exc()}
    finally:
        sys.stdout = old_stdout
