# coding=utf-8
'''

Date: 2016-12-29
Time: 11:13:11
Author: Yanjiasen4

This is a werewolf robots of QQ group

'''
import re

from random import randint,shuffle
from smart_qq_bot.signals import on_bot_inited
from smart_qq_bot.signals import on_all_message
from smart_qq_bot.messages import (
    QMessage,
    GroupMsg,
    PrivateMsg,
    SessMsg,
    DiscussMsg,
)
from smart_qq_bot.logger import logger

GAMESTATE = {
    'INIT': 0,
    'IDLE': 1,
    'ENROLLING': 2,
    'WAITING': 3,
    'NIGHT': 4,
    'WITCH_TURN_1': 5,
    'WITCH_TURN_2': 6,
    'SEER_TURN': 7,
    'DAY': 8,
    'VOTE': 9
}
GAMEMODE = {
    'SLAY_PART': 1,
    'SLAY_ALL': 2
}
CMDTABLE = {
    'start': '!start',
    'enroll': '!ge',
    'step': '!go',
    'query_role': '!me',
    'kill': '!kill',
    'heal': '!heal',
    'poison': '!poison',
    'giveup': '!no',
    'check': '!check',
    'police': '!p',
    'vote': '!v',
    'execute': '!exe',
    'shot': '!shot',
    #DEBUG CMD
    'show': '!show'
}
ROLESTABLE = ['werewolf', 'villager', 'hunter', 'witch', 'seer']
GODTABLE = ['hunter','witch','seer']
ROLESMAP = {
    'null': -1,
    'werewolf': 0,
    'villager': 1,
    'hunter': 2,
    'witch': 3,
    'seer': 4
}
ROLESMAPCN = {
    'null': '无',
    'werewolf': '狼人',
    'villager': '村民',
    'hunter': '猎人',
    'witch': '女巫',
    'seer': '预言家'
}
PLAYERSTATE = {
    'alive': 1,
    'killed': 2,
    'poison': 3,
    'dead': 4
}
HELPTABLE = {
    'werewolf': '请和你的狼队友讨论今晚猎杀的目标，决定后任意一个人私聊我 !kill玩家编号 来执行',
    'seer': '请选择今晚你想查验身份的人，输入 !check玩家编号 来执行',
    'witch1': '你有一瓶解药，要用吗？输入 !heal 来执行，输入 !no 放弃',
    'witch2': '你有一瓶毒药，要用它来毒死谁吗？输入 !poison玩家编号 来执行，输入 !no 放弃',
    'hunter': '很不幸，我们的猎人死了，他可以选择带走一个玩家。输入 !shot玩家编号 执行，输入 !giveup 放弃'
}

class Player(object):
    '''
    Class: Player

    '''
    def __init__(self, card, name, id, nid, role):
        self.player_card = card
        self.player_name = name
        self.player_id = id
        self.player_uin = None
        self.player_nid = nid
        self.player_role = role
        self.player_confirm = False
        self.player_state = PLAYERSTATE['alive']

    def dead(self):
        self.player_state = PLAYERSTATE['dead']

    def heal(self):
        if self.player_state == PLAYERSTATE['killed']:
            self.player_state = PLAYERSTATE['alive']

    def setUin(self, uin):
        self.player_uin = uin

class WereWolf(object):

    def __init__(self):
        self._key_regex = re.compile("^!start|!ge|!me|!kill|!heal|!poison|!no|!check|!v|!exe|!shot|!show")
        self.state = GAMESTATE['IDLE']
        self.pre_state = GAMESTATE['INIT']
        self.rolesNum = 0
        self.confirmNum = 0
        self.players = []
        self.roles = {}
        self.roles_pool = []
        self.game_mode = GAMEMODE['SLAY_ALL']
        self.active_content = ""
        self.active_receiver = []
        self.group_code = ""
        self.heal = True
        self.poison = True
        self.round = 0
        self.sheriff_nid = -1
    
    def parseAndExcuteMsg(self, msg, id):
        if self.state > GAMESTATE['WAITING']:
            gs = self.judge_win()
            if gs == 1:
                return 0, "恭喜好人获得胜利!\n" + self.get_player_info(1)
            elif gs == 2:
                return 0, "恭喜狼人获得胜利!\n" + self.get_player_info(1)
        logger.info(msg.content)
        content = msg.content
        content = content.replace(' ','')
        result = re.findall(self._key_regex, content)
        reply = ""
        mode = 0
        if result:
            cmd = result[0]
            para = msg.content[len(cmd):]
            logger.info(para)
            mode, reply = self.excuteMsg(cmd, para, msg, id)
        return mode, reply

    def excuteMsg(self, cmd, para=None, msg=None, id=None):
        mode = 0
        reply = ""
        # special cmd
        if cmd == CMDTABLE['show']:
            if self.state != GAMESTATE['IDLE']:
                mode, reply = self.do_show_player_info()
        
        if self.state == GAMESTATE['IDLE']:
            if cmd == CMDTABLE['start']:
                self.group_code = msg.group_code
                mode, reply = self.do_start(para)
        elif self.state == GAMESTATE['ENROLLING'] or self.state == GAMESTATE['WAITING']:
            if cmd == CMDTABLE['enroll']:
                if isinstance(msg, GroupMsg):
                    sender_card = msg.src_sender_card
                    sender_name = msg.src_sender_name
                    sender_id = msg.src_sender_id
                    mode, reply = self.do_enroll(sender_card, sender_name, sender_id)
                elif isinstance(msg, PrivateMsg):
                    mode = 0
                    reply = "这么想和人家偷偷聊天呀？~~报名还是要在群里的哟(＾Ｕ＾)ノ~"
                else:
                    reply = "未知错误"
            if cmd == CMDTABLE['query_role']:
                if isinstance(msg, PrivateMsg):
                    player = self.get_player(id)
                    if player:
                        if player.player_uin is None:
                            logger.info(msg.from_uin)
                            player.setUin(msg.from_uin)
                        mode, reply = self.do_query_role(id)
                elif isinstance(msg, GroupMsg):
                    reply = "查看身份请发送 !me 私戳我<3"
        elif self.state == GAMESTATE['NIGHT']:
            if cmd == CMDTABLE['kill'] and isinstance(msg, PrivateMsg):
                mode, reply = self.do_kill(int(para))
        elif self.state == GAMESTATE['WITCH_TURN_1']:
            if cmd == CMDTABLE['heal'] and isinstance(msg, PrivateMsg):
                mode, reply = self.do_heal()
            elif cmd == CMDTABLE['giveup'] and isinstance(msg, PrivateMsg):
                self.next_state()
                self.gen_active_content()
                mode = 1
        elif self.state == GAMESTATE['WITCH_TURN_2']:
            if cmd == CMDTABLE['poison'] and isinstance(msg, PrivateMsg):
                mode, reply = self.do_poison(int(para))
            elif cmd == CMDTABLE['giveup'] and isinstance(msg, PrivateMsg):
                self.next_state()
                self.gen_active_content()
                mode = 1
        elif self.state == GAMESTATE['SEER_TURN']:
            if cmd == CMDTABLE['check'] and isinstance(msg, PrivateMsg):
                mode, reply = self.do_check(int(para))
        elif self.state == GAMESTATE['DAY']:
            if cmd == CMDTABLE['police'] and isinstance(msg, GroupMsg):
                mode, reply = self.do_become_sheriff(nid)
        elif self.state == GAMESTATE['VOTE']:
            if cmd == CMDTABLE['execute'] and isinstance(msg, GroupMsg):
                mode, reply = self.do_execute(nid)
            if cmd == CMDTABLE['shot'] and isinstance(msg, GroupMsg):
                mode, reply = self.do_shot(nid)
        return mode, reply
            
    def do_start(self, para):
        logger.info("---------------Start a game----------------")
        paras = para.split(',')
        reply = "本局阵容为:\n"
        l = 0
        logger.info(paras)
        for r in paras[:-1]:
            i = int(r)
            if i == 0:
                l = l + 1 
                continue
            self.roles[ROLESTABLE[l]] = i
            self.rolesNum = self.rolesNum + i
            for k in range(i):
                self.roles_pool.append(ROLESTABLE[l])
            reply = reply + ROLESMAPCN[ROLESTABLE[l]] + ": " + r + "\n"
            logger.info(ROLESTABLE[l] + ": " + r)
            l = l + 1
        
        if int(paras[len(paras)-1]) == 1:
            self.game_mode = GAMEMODE['SLAY_PART']
            reply = reply + "规则为屠边\n"
        else:
            self.game_mode = GAMEMODE['SLAY_ALL']
            reply = reply + "规则为屠城\n"
        reply = reply + "参加游戏请输入 !ge 报名\n" + "报名后私聊我 !me 查看自己的身份"
        self.next_state()
        self.shuffle_roles()
        return 0, reply
    
    def do_enroll(self, card, name, id):
        needPlayers = self.rolesNum - len(self.players)
        logger.info(needPlayers)
        if needPlayers == 0:
            content = "我们人满了，你来晚了!"
            logger.info(content)
            return 0, content
        else:
            if self.get_player(id) is None:
                player = Player(card, name, id, len(self.players)+1, self.roles_pool.pop())
                self.players.append(player)
                needPlayers = needPlayers - 1
                if needPlayers == 0:
                    content = str(id) + "-" + name + " 报名成功!\n" + "游戏人数已满，请大家输入 !me 私戳本上帝确认自己身份"
                    self.next_state()
                else:
                    content = str(id) + "-" + name + " 报名成功!\n" + "还需要" + str(needPlayers) + "个鸽友游戏才能开始"
            else:
                content = str(id) + "-" + name + " 请大家不要重复报名，这样本上帝会很苦恼的啦ε=( o｀ω′)ノ!\n"
            return 0, content

    def do_query_role(self, id):
        player = self.get_player(id)
        if player:
            player.player_confirm = True
            self.confirmNum = self.confirmNum + 1
            content = player.player_name + " 你的身份是: " + ROLESMAPCN[player.player_role] + "\n"
            logger.info(content)
            if player.player_role == 'werewolf':
                wereloves = self.get_player_werewolves()
                if len(wereloves) > 1:
                    content += "你的狼人队友是： "
                    for w in wereloves:
                        if w.player_id != str(id):
                            content = content + str(w.player_nid) + "号: " + w.player_name + "\n"
                elif len(wereloves) == 1:
                    content += "你是一匹孤独的狼，强者都是孤独的，试着赢得这场游戏吧!"
            else:
                pass

            if self.confirmNum == self.rolesNum:
                self.next_state()
                self.round = 1
                self.gen_active_content()

            return 1, content
        else:
            return 0, "亲，你还没有报名哟(⊙﹏⊙)"

    def do_kill(self, nid):
        logger.info(type(nid))
        logger.info(nid)
        if nid < 1 or nid > self.rolesNum:
            return 0, "目标编号错误，请重新选择"
        player = self.get_player_by_nid(nid)
        content = ""
        mode = 1
        if player:
            if player.player_state != PLAYERSTATE['dead']:
                player.player_state = PLAYERSTATE['killed']
                self.next_state()
                self.gen_active_content()
                mode = 1
            else:
                content = "不要鞭尸了，他已经是个死人了"
        return mode, content

    def do_heal(self):
        if self.get_player_by_role('witch') is None:
            self.state = GAMESTATE['SEER_TURN']
        else:
            if self.heal == False:
                return 0, "你的解药已经用完了"
            player = self.get_player_killed()
            if player:
                player.player_state = PLAYERSTATE['alive']
                self.heal = False
                self.next_state()
        self.gen_active_content()
        return 1, ""

    def do_poison(self, nid):
        if self.poison == False:
            return 0, "你的毒药已经用完了"
        player = self.get_player(nid)
        content = ""
        if player:
            if player.player_state != PLAYERSTATE['dead']:
                player.player_state = PLAYERSTATE['poison']
                self.poison = False
                self.next_state()
                self.gen_active_content()
                return 2, ""
            else:
                content = "不要鞭尸了，他已经是个死人了"
        else:
            content = "咱好好选人行吗"
        return 0, content
    
    def do_check(self, nid):
        player = self.get_player(nid)
        content = str(player.player_nid) + "号玩家:" + player.player_name + " 是 "
        if player:
            if player.player_state != PLAYERSTATE['dead']:
                if player.player_role != 'werewolf':
                    content = content + " 好人"
                else:
                    content = content + " 狼人"
                self.next_state()
                self.gen_active_content()
                return 2, content
            else:
                content = "死人是不会说话的......\n请重新选择你要查验的对象\n" + HELPTABLE['seer']
        return 0, content

    def do_become_sheriff(self, nid):
        player = self.get_player(nid)
        content = ""
        if player:
            if player.player_state != PLAYERSTATE['dead']:
                self.sheriff_nid = nid
                content = str(player.player_nid) + "号玩家:" + player.player_name + "成为了警长\n"
                self.next_state()
                self.gen_active_content()
            else:
                content = "死人别出来捣乱了"
        return 2, content
    
    def do_shot(self, id, nid):
        hunter = self.get_player_by_role('hunter')
        if len(hunter) == 0:
            return 0, ""
        if str(hunter.player_id) != str(id):
            return 0, ""

        player = self.get_player_by_nid(nid)
        if not player:
            return 0, ""
        if player.player_state != PLAYERSTATE['alive']:
            return 0, str(player.player_nid) + "号玩家已经死啦，不要鞭尸啦"
        else:
            player.player_state = PLAYERSTATE['dead']:
            return 0, str(player.player_nid) + "号玩家被猎人一枪崩死，真是惨"
        return 0, ""

    def do_execute(self, nid):
        player = self.get_player(nid)
        content = ""
        if player:
            content = str(nid) + "号玩家被投票处死 "
            player.player_state = PLAYERSTATE['dead']
            self.next_state()
        else:
            content = "输入玩家序号不存在，请重新输入"
        return 0, content

    def judge_win(self):
        '''
        return: 
        1 好人赢
        2 狼人赢
        '''
        if self.game_mode == GAMEMODE['SLAY_PART']:
            if (self.check_player_god() or self.check_player_civilian()):
                return 2
            if self.check_player_werewolf():
                return 1
        if self.game_mode == GAMEMODE['SLAY_ALL']:
            if self.check_player_goodman():
                return 2
            if self.check_player_werewolf():
                return 1
        return 0

    def gen_active_content(self):
        if self.state == GAMESTATE['NIGHT']:
            self.active_content = HELPTABLE['werewolf'] + "\n" + self.get_player_info()
            self.active_receiver = self.get_player_werewolves()
        elif self.state == GAMESTATE['WITCH_TURN_1']:
            victim = self.get_player_killed()
            self.active_content = "昨天晚上 " + str(victim.player_nid) + " 号玩家 " + victim.player_name + " 被杀了\n" + HELPTABLE['witch1']
            self.active_receiver = self.get_player_by_role("witch")
        elif self.state == GAMESTATE['WITCH_TURN_2']:
            self.active_content = HELPTABLE['witch2']
            self.active_receiver = self.get_player_by_role("witch")
        elif self.state == GAMESTATE['SEER_TURN']:
            self.active_content = HELPTABLE['seer']
            self.active_receiver = self.get_player_by_role("seer")
        elif self.state == GAMESTATE['DAY']:
            self.active_content = "天亮了，开始竞选警长啦!竞选出来的警长请在群里输入 !p 让本上帝知道"
            self.active_receiver = self.group_code
        elif self.state == GAMESTATE['VOTE']:
            content = "昨天晚上"
            victim = self.get_player_deading()
            if victim:
                content += ":\n"
                for player in victim:
                    content += str(player.player_nid) + "号玩家" + player.player_name + "死了\n"
            else:
                content += "是个平安夜"
            self.active_content = content
            self.active_receiver = self.group_code
    
    def next_state(self):
        self.pre_state = self.state
        if self.state == GAMESTATE['NIGHT']:
            if len(self.get_player_by_role('witch')) == 0:
                self.state = GAMESTATE['SEER_TURN'] - 1
        if self.state == GAMESTATE['SEER_TURN']:
            if len(self.get_player_by_role('seer')) == 0:
                self.state = GAMESTATE['DAY'] - 1
        if self.state == GAMESTATE['EXECUTE']:
            self.round = self.round + 1
            self.state = GAMESTATE['NIGHT'] - 1
        self.state = self.state + 1

    def shuffle_roles(self):
        '''洗牌'''
        shuffle(self.roles_pool)

    def get_player(self, id):
        logger.info("query id: " + str(id))
        for player in self.players:
            logger.info(player.player_id)
            logger.info(type(id))
            if int(player.player_id) == int(id):
                logger.info("get player" + str(id))
                return player
        logger.info("player not exists")
        return None

    def get_player_by_nid(self, nid):
        for player in self.players:
            if int(player.player_nid) == int(nid):
                return player
        return None

    def get_player_werewolves(self):
        werewolves = []
        for player in self.players:
            if player.player_role == 'werewolf':
                werewolves.append(player)
        return werewolves

    def get_player_goodman(self):
        goodmen = []
        for player in self.players:
            if player.player_role != 'werewolf':
                goodmen.append(player)
        return goodmen
    
    def get_player_god(self):
        gods = []
        for player in self.players:
            if player.player_role in GODTABLE:
                gods.append(player)
        return gods

    def get_player_civilian(self):
        civilian = []
        goodman = self.get_player_goodman()
        for player in goodman:
            if player.player_role not in GODTABLE:
                civilian.append(player)
        return civilian

    def get_player_by_role(self, role):
        players = []
        for player in self.players:
            if player.player_role == role:
                players.append(player)
        return players

    def get_player_killed(self):
        for player in self.players:
            if player.player_state == PLAYERSTATE['killed']:
                return player
        return None

    def get_player_deading(self):
        dead = []
        for player in self.players:
            if player.player_state == PLAYERSTATE['killed'] or player.player_state == PLAYERSTATE['poison']:
                dead.append(player)
        return dead
    
    def check_player_goodman(self):
        goodmen = self.get_player_goodman()
        for player in goodmen:
            if player.player_state != PLAYERSTATE['dead']:
                return False
        return True

    def check_player_god(self):
        '''
        return False if any gods alive
        '''
        gods = self.get_player_god()
        if len(gods) == 0: return False
        for player in gods:
            if player.player_state != PLAYERSTATE['dead']:
                 return False
        return True

    def check_player_civilian(self):
        '''
        return False if any civilian alive
        '''
        civilian = self.get_player_civilian()
        if len(civilian) == 0: return False
        for player in civilian:
            if player.player_state != PLAYERSTATE['dead']:
                return False
        return True

    def check_player_werewolf(self):
        '''
        return False if any werewolves alive
        '''
        werewolves = self.get_player_werewolves()
        if len(werewolves) == 0: return False
        for player in werewolves:
            if player.player_state != PLAYERSTATE['dead']:
                return False
        return True

    def do_show_player_info(self):
        content = self.get_player_info(1)
        return 1, content
    
    def get_group_code(self):
        pass

    def get_player_info(self, mode=0):
        if mode == 0:
            content = "玩家序号   QQ昵称\n"
            for player in self.players:
                content = content + str(player.player_nid) + "   " + str(player.player_name) + "\n"
        elif mode == 1:
            content = "玩家序号   QQ昵称     身份\n"
            for player in self.players:
                content = content + str(player.player_nid) + " " + str(player.player_name) + " " + player.player_role + "\n"
        return content[:-1]

    def run(self, msg, id):
        return self.parseAndExcuteMsg(msg, id)

    def startGame(self):
        pass

wwBot = WereWolf()

@on_bot_inited("PluginManager")
def manager_init(bot):
    logger.info("Plugin Manager is available now:)")

@on_all_message(name="wereWolfBot")
def wereWolfBot(msg, bot):
    """
    :type bot: smart_qq_bot.bot.QQBot
    :type msg: smart_qq_bot.messages.GroupMsg
    """
    sender_id = bot.uin_to_account(msg.from_uin)
    logger.info(msg.from_uin)
    logger.info(sender_id)
    mode, reply = wwBot.run(msg, sender_id)
    logger.info("_______________current state: " + str(wwBot.state))
    logger.info(mode)
    if reply:
        bot.reply_msg(msg, reply)
    if mode == 0:
        pass
    elif mode == 1:
        logger.info("???")
        logger.info(wwBot.active_content)
        logger.info(wwBot.active_receiver)
        for recevier in wwBot.active_receiver:
            msg_id = randint(1,10000)
            bot.send_friend_msg(wwBot.active_content, recevier.player_uin, msg_id)
    elif mode == 2:
        logger.info(wwBot.active_content)
        logger.info(wwBot.active_receiver)
        msg_id = randint(1,10000)
        bot.send_group_msg(wwBot.active_content, recevier, msg_id)
    elif expression:
        pass

