import tdl
from random import randint
import colors
import math
import textwrap

turnCount=0

# actual size of the window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

# size of the map
MAP_WIDTH = 80
MAP_HEIGHT = 43

# sizes and coordinates relevant for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

# parameters for dungeon generator
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 3
MAX_ROOM_ITEMS = 2

FOV_ALGO = 'BASIC'
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

LIMIT_FPS = 20  # 20 frames-per-second maximum

INVENTORY_WIDTH = 50

HEAL_AMOUNT = randint(6, 10)

LIGHTNING_DAMAGE = 20
LIGHTNING_RANGE = 5

CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8

LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 100
LEVEL_SCREEN_WIDTH = 40

CHARACTER_SCREEN_WIDTH = 40

color_dark_ground = (5, 35, 5)
color_light_ground = (40, 70, 45)
color_dark_wall = (85, 85, 85)
color_light_wall = (123, 122, 129)

monster_chances = {'orc': 80, 'troll': 20}
item_chances = {'heal': 55, 'lightning': 15, 'confuse': 15, 'roulette': 15}


class Tile:
    # a tile of the map and its properties
    def __init__(self, blocked, block_sight=None):
        self.blocked = blocked

        # all tiles start unexplored
        self.explored = False

        # by default, if a tile is blocked, it also blocks sight
        if block_sight is None:
            block_sight = blocked
        self.block_sight = block_sight


class Rect:
    # a rectangle on the map. used to characterize a room.
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2) // 2
        center_y = (self.y1 + self.y2) // 2
        return (center_x, center_y)

    def intersect(self, other):
        # returns true if this rectangle intersects with another one
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)


class GameObject:
    # this is a generic object: the player, a monster, an item, the stairs...
    # it's always represented by a character on screen.
    def __init__(self, x, y, char, name, color, blocks=False,
                 fighter=None, ai=None, item=None):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks = blocks
        self.fighter = fighter


        if self.fighter:  # let the fighter component know who owns it
            self.fighter.owner = self

        self.ai = ai
        if self.ai:  # let the AI component know who owns it
            self.ai.owner = self

        self.item = item
        if self.item:
            self.item.owner = self

    def move(self, dx, dy):
        # move by the given amount, if the destination is not blocked
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def move_towards(self, target_x, target_y):
        # vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # normalize it to length 1 (preserving direction), then round it and
        # convert to integer so the movement is restricted to the map grid
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)

    def distance_to(self, other):
        # return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def send_to_back(self):
        # make this object be drawn first, so all others appear above it if they're in the same tile.
        global objects
        objects.remove(self)
        objects.insert(0, self)

    def draw(self):
        global visible_tiles

        # only show if it's visible to the player
        if (self.x, self.y) in visible_tiles:
            # draw the character that represents this object at its position
            con.draw_char(self.x, self.y, self.char, self.color, bg=None)

    def clear(self):
        # erase the character that represents this object
        con.draw_char(self.x, self.y, ' ', self.color, bg=None)

    def distance(self, x, y):
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

class Fighter:
    # combat-related properties and methods (monster, player, NPC).
    def __init__(self, hp, defense, power, xp, death_function=None, health_color=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.death_function = death_function
        self.xp = xp
        self.health_color = health_color

    def take_damage(self, damage):
        # apply damage if possible
        if damage > 0:
            self.hp -= damage

            # check for death. if there's a death function, call it
            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner)
                if self.owner != player:
                    player.fighter.xp += self.xp

            elif self.hp <= self.hp / 2:
                function = self.health_color
                if function is not None:
                    function(self.owner)

    def attack(self, target):
        # a simple formula for attack damage
        damage = self.power - target.fighter.defense

        if damage > 0:
            # make the target take some damage
            message(self.owner.name.capitalize() + ' attacks ' + target.name +
                    ' for ' + str(damage) + ' hit points.')
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name +
                    ' but it has no effect!')

    def heal(self, amount):
        #heal by the given amount, without going over the maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

class BasicMonster:
    # AI for a basic monster.
    def take_turn(self):
        # a basic monster takes its turn. If you can see it, it can see you
        monster = self.owner
        if (monster.x, monster.y) in visible_tiles:

            # move towards player if far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)

            # close enough, attack! (if the player is still alive.)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)

class Item:
    def __init__(self, use_function=None):
        self.use_function = use_function

    def use(self):
        # just call the use_fucntion if it's defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner)  # destroy after use

    def heal(self, amount):
        #heal by the given amount, without going over the maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

    # an item that can be picked up and used.
    def pick_up(self):
        # add to the player's inventory and remove from the map
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', colors.red)
        elif len(inventory) < 26:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', colors.green)
    def drop(self):
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', colors.yellow)

class ConfusedMonster:
    #AI for a temporarily confused monster (reverts to previous AI after a while).
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0:  # still confused..
              # random move, then decrease the number of turns left to be confused
            self.owner.move(randint(-1, 1), randint(-1, 1))
            self.num_turns -= 1

        else:    # restore the prev AI (delete this ai cuz its not referenced anymore)
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is not longer confused!', colors.red)

def target_monster(max_range=None):
    while True:
        (x, y) = target_tile(max_range)
        if x is None:
            return None
        for object in objects:
            if object.x == x and object.y == y and object.fighter and object != player:
                return object

def cast_roulette():
    #heal for 1 or somethimes for full
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', colors.red)
        return 'cancelled'
    message('You roll the dice!', colors.light_cyan)
    roulette = randint(1,3)
    if roulette == 1:
        player.fighter.heal(player.fighter.max_hp)
    elif roulette >= 2:
        player.fighter.heal(-2)

def cast_heal():
    # heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', colors.red)
        return 'cancelled'
    message('Your wounds start to feel better!', colors.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
    # find closest enemy inside a range, and smite that bitch!
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None:
        message('No enemy is close enough to strike.', colors.red)
        return 'cancelled'

    # ZAP IT
    message('A lightning bolt strikes the' + monster.name + ' with a loud thunder! The damage is '
             + str(LIGHTNING_DAMAGE) + ' hit points.', colors.light_blue)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)

def cast_confuse():
    message('Left-click an enemy to confuse it, or right-click to cancel.', colors.light_cyan)
    monster = closest_monster(CONFUSE_RANGE)
    if monster is None:
        message('Cancelled.')
        return 'cancelled'
    # replace the monster's AI with a confused one, after some turns, return the old AI
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster  # tell the new component who owns it
    message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', colors.light_green)


def target_tile(max_range=None):
    # return the position of a tile left-clicked in player's FOV (optionally in
    # a range), or (None,None) if right-clicked.
    global mouse_coord

    clicked = False
    for event in tdl.event.get():
        if event.type == 'MOUSEMOTION':
            mouse_coord = event.cell
        if event.type == 'MOUSEDOWN' and event.button == 'LEFT':
            clicked = True
        elif ((event.type == 'MOUSEDOWN' and event.button == 'RIGHT') or
                  (event.type == 'KEYDOWN' and event.key == 'ESCAPE')):
            return (None, None)
    render_all()

    if clicked:
        return mouse_coord

def closest_monster(max_range):

    # find closest enemy, up to a maximum, and in the players fov
    closest_monster= None
    closest_dist = max_range + 1

    for object in objects:
        if object.fighter and not object == player and (object.x, object.y) in visible_tiles:
            dist = player.distance_to(object)
            if dist < closest_dist:
                closest_monster = object
                closest_dist = dist
    return closest_monster

def is_blocked(x, y):
    # first test the map tile
    if my_map[x][y].blocked:
        return True

    # now check for any blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True

    return False


def create_room(room):
    global my_map
    # go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            my_map[x][y].blocked = False
            my_map[x][y].block_sight = False


def create_h_tunnel(x1, x2, y):
    global my_map
    for x in range(min(x1, x2), max(x1, x2) + 1):
        my_map[x][y].blocked = False
        my_map[x][y].block_sight = False


def create_v_tunnel(y1, y2, x):
    global my_map
    # vertical tunnel
    for y in range(min(y1, y2), max(y1, y2) + 1):
        my_map[x][y].blocked = False
        my_map[x][y].block_sight = False


def is_visible_tile(x, y):
    global my_map

    if x >= MAP_WIDTH or x < 0:
        return False
    elif y >= MAP_HEIGHT or y < 0:
        return False
    elif my_map[x][y].blocked == True:
        return False
    elif my_map[x][y].block_sight == True:
        return False
    else:
        return True


def make_map():
    global my_map, objects, stairs

    # fill map with "blocked" tiles
    my_map = [[Tile(True)
               for y in range(MAP_HEIGHT)]
              for x in range(MAP_WIDTH)]

    rooms = []
    objects = [player]
    num_rooms = 0

    for r in range(MAX_ROOMS):
        # random width and height
        w = randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        # random position without going out of the boundaries of the map
        x = randint(0, MAP_WIDTH - w - 1)
        y = randint(0, MAP_HEIGHT - h - 1)

        # "Rect" class makes rectangles easier to work with
        new_room = Rect(x, y, w, h)

        # run through the other rooms and see if they intersect with this one
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:
            # this means there are no intersections, so this room is valid

            # "paint" it to the map's tiles
            create_room(new_room)

            # center coordinates of new room, will be useful later
            (new_x, new_y) = new_room.center()

            if num_rooms == 0:
                # this is the first room, where the player starts at
                player.x = new_x
                player.y = new_y

            else:
                # all rooms after the first:
                # connect it to the previous room with a tunnel

                # center coordinates of previous room
                (prev_x, prev_y) = rooms[num_rooms - 1].center()

                # draw a coin (random number that is either 0 or 1)
                if randint(0, 1):
                    # first move horizontally, then vertically
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    # first move vertically, then horizontally
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)

            # add some contents to this room, such as monsters
            place_objects(new_room)

            # finally, append the new room to the list
            rooms.append(new_room)
            num_rooms += 1
    stairs = GameObject(new_x, new_y, '>', 'stairs', colors.white)
    objects.append(stairs)
    stairs.send_to_back()

def place_objects(room):
    global health_color
    # choose random number of monsters
    num_monsters = randint(0, MAX_ROOM_MONSTERS)

    for i in range(num_monsters):
        # choose random spot for this monster
        x = randint(room.x1+1, room.x2-1)
        y = randint(room.y1+1, room.y2-1)

        # only place it if the tile is not blocked
        if not is_blocked(x, y):
            if dungeon_level <= 3:
                if randint(0, 100) < 80:  # 80% chance of getting a rat
                    # create a rat
                    fighter_component = Fighter(hp=5, defense=0, power=randint(2, 4), xp=5,
                                                death_function=monster_death, health_color=health_color)
                    ai_component = BasicMonster()

                    monster = GameObject(x, y, 'r', 'rat', colors.light_grey,
                                        blocks=True, fighter=fighter_component, ai=ai_component)
                else:
                    # create an orc
                    fighter_component = Fighter(hp=12, defense=0, power=randint(4, 6), xp=20,
                                                death_function=monster_death, health_color=health_color)
                    ai_component = BasicMonster()

                    monster = GameObject(x, y, 'o', 'orc', colors.desaturated_yellow,
                                        blocks=True, fighter=fighter_component, ai=ai_component)
            elif dungeon_level > 3:
                if randint(0, 100) < 80:  # 80% chance of getting an orc
                    # create an orc
                    fighter_component = Fighter(hp=12, defense=0, power=randint(4, 6), xp=20,
                                                death_function=monster_death, health_color=health_color)
                    ai_component = BasicMonster()

                    monster = GameObject(x, y, 'o', 'orc', colors.desaturated_yellow,
                                        blocks=True, fighter=fighter_component, ai=ai_component)
                else:
                    # create a troll
                    fighter_component = Fighter(hp=18, defense=1, power=randint(6, 8), xp=50,
                                                death_function=monster_death, health_color=health_color)
                    ai_component = BasicMonster()

                    monster = GameObject(x, y, 'T', 'troll', colors.darker_green,
                                        blocks=True, fighter=fighter_component, ai=ai_component)

            elif dungeon_level > 5:
                if randint(0, 100) < 60:  # 60% chance of getting an orc
                    # create an orc
                    fighter_component = Fighter(hp=12, defense=0, power=randint(4, 6), xp=20,
                                                death_function=monster_death, health_color=health_color)
                    ai_component = BasicMonster()

                    monster = GameObject(x, y, 'o', 'orc', colors.desaturated_yellow,
                                        blocks=True, fighter=fighter_component, ai=ai_component)
                elif randint(0,100) < 80: #20% chance of getting a zombie
                    # create a troll
                    fighter_component = Fighter(hp=30, defense=2, power=randint(4, 7), xp=70,
                                                death_function=monster_death, health_color=health_color)
                    ai_component = BasicMonster()

                    monster = GameObject(x, y, 'Z', 'zombie', colors.dark_green,
                                        blocks=True, fighter=fighter_component, ai=ai_component)

                else:
                    # create a troll
                    fighter_component = Fighter(hp=18, defense=1, power=randint(6, 8), xp=50,
                                                death_function=monster_death, health_color=health_color)
                    ai_component = BasicMonster()

                    monster = GameObject(x, y, 'T', 'troll', colors.darker_green,
                                        blocks=True, fighter=fighter_component, ai=ai_component)

            objects.append(monster)

    num_items = randint(0, MAX_ROOM_ITEMS)

    for i in range(num_items):
            # choose a random spot for this item
        x = randint(room.x1+1, room.x2-1)
        y = randint(room.y1+1, room.y2-1)

    # place if tile is not blocked
        if not is_blocked(x, y):
            dice = randint(0, 100)
            if dice < 60:
                # create a health potion (60% chance)
                item_component = Item(use_function=cast_heal)
                item = GameObject(x, y, '!', 'healing potion', colors.darker_red, item=item_component)
            elif dice < 60+10:
                # create a lightning bolt scroll (10% chance)
                item_component = Item(use_function=cast_lightning)
                item = GameObject(x, y, '#', 'scroll of lightning bolt', colors.light_cyan, item=item_component)
            elif dice < 60+10+10:
                # create a confuse scroll (10% chance)
                item_component = Item(use_function=cast_confuse)
                item = GameObject(x, y, '#', 'scroll of confusion', colors.light_yellow, item=item_component)
            elif dice < 60+10+10+10+10:
                # create a roulette potion (10% chance)
                item_component = Item(use_function=cast_roulette)
                item = GameObject(x, y, '%', 'roulette potion', colors.light_violet, item=item_component)

            objects.append(item)
            item.send_to_back()    # items appear below other objects

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    # render a bar (HP, experience, etc). first calculate the width of the bar
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    bar_width = int(float(value) / maximum * total_width)

    # render the background first
    panel.draw_rect(x, y, total_width, 1, None, bg=back_color)

    # now render the bar on top
    if bar_width > 0:
        panel.draw_rect(x, y, bar_width, 1, None, bg=bar_color)

    # finally, some centered text with the values
    xp_text = 'XP: ' + str(player.fighter.xp) + '/' + str(level_up_xp)
    hp_text = name + ': ' + str(value) + '/' + str(maximum)
    x_centered = x + (total_width - len(hp_text)) // 2
    panel.draw_str(x_centered, y, hp_text, fg=colors.white, bg=None)
    #panel.draw_str(x_centered, y+1, xp_text, fg=colors.white, bg=None)


def get_names_under_mouse():
    global visible_tiles
    # return a string with the names of all objects under the mouse
    (x, y) = mouse_coord

    # create a list with the names of all objects at the mouse's coordinates and in FOV
    names = [object.name for object in objects
             if object.x == x and object.y == y and (object.x, object.y) in visible_tiles]

    names = ', '.join(names)  # join the names, separated by commas
    return names.capitalize()


def render_all():
    global fov_recompute, dungeon_level, stairs
    global visible_tiles

    if fov_recompute:
        fov_recompute = False
        visible_tiles = tdl.map.quick_fov(player.x, player.y,
                                         is_visible_tile,
                                         fov=FOV_ALGO,
                                         radius=TORCH_RADIUS,
                                         lightWalls=FOV_LIGHT_WALLS)

        # go through all tiles, and set their background color according to the FOV
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = (x, y) in visible_tiles
                wall = my_map[x][y].block_sight
                if not visible:
                    # if it's not visible right now, the player can only see it if it's explored
                    if my_map[x][y].explored:
                        if wall:
                            con.draw_char(x, y, None, fg=None, bg=color_dark_wall)
                        else:
                            con.draw_char(x, y, None, fg=None, bg=color_dark_ground)
                else:
                    if wall:
                        con.draw_char(x, y, None, fg=None, bg=color_light_wall)
                    else:
                        con.draw_char(x, y, None, fg=None, bg=color_light_ground)
                    # since it's visible, explore it
                    my_map[x][y].explored = True

    # draw all objects in the list
    for obj in objects:
        if obj != player:
            obj.draw()
    player.draw()
    # blit the contents of "con" to the root console and present it
    root.blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0)

    # prepare to render the GUI panel
    panel.clear(fg=colors.white, bg=colors.black)

    # print the game messages, one line at a time
    y = 1
    for (line, color) in game_msgs:
        panel.draw_str(MSG_X, y, line, bg=None, fg=color)
        y += 1

    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR

    # show the player's stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
               colors.light_red, colors.darker_red)
    render_bar(1, 3, BAR_WIDTH, 'XP', player.fighter.xp, level_up_xp, colors.orange, colors.desaturated_yellow)

    panel.draw_str(1, 0, "Dungeon Level:" + ' ' + str(dungeon_level), bg=None, fg=colors.light_grey)

    panel.draw_str(1, 5, "Turn Count:" + ' ' + str(turnCount), bg=None, fg=colors.light_grey)

    # display names of objects under the mouse
    panel.draw_str(1, 0, get_names_under_mouse(), bg=None, fg=colors.light_gray)

    # blit the contents of "panel" to the root console
    root.blit(panel, 0, PANEL_Y, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0)


def message(new_msg, color=colors.white):
    # split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        # if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]

        # add the new line as a tuple, with the text and the color
        game_msgs.append((line, color))

def player_move_or_attack(dx, dy):
    global fov_recompute

    # the coordinates the player is moving to/attacking
    x = player.x + dx
    y = player.y + dy

    # try to find an attackable object there
    target = None
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break

    # attack if target found, move otherwise
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True

def handle_keys():
    global playerx, playery, dungeon_level, stairs
    global fov_recompute, level_up_xp
    global mouse_coord

    keypress = False

    for event in tdl.event.get():
        if event.type == 'KEYDOWN' and not event.text:
            user_input = event
            keypress = True
        if event.type == 'MOUSEMOTION':
            mouse_coord = event.cell

    if not keypress:
        return 'didnt-take-turn'

    if user_input.key == 'ENTER' and user_input.alt:
        # Alt+Enter: toggle fullscreen
        tdl.set_fullscreen(True)

    elif user_input.key == 'ESCAPE':
        return 'exit'  # exit game

    if game_state == 'playing':
        # movement keys
        if user_input.keychar == 'w':
            player_move_or_attack(0, -1)

        elif user_input.keychar == 's':
            player_move_or_attack(0, 1)

        elif user_input.keychar == 'a':
            player_move_or_attack(-1, 0)

        elif user_input.keychar == 'd':
            player_move_or_attack(1, 0)

        else:
            if user_input.keychar == 'g':
                for obj in objects:  # look for an item in the player's tile
                    if obj.x == player.x and obj.y == player.y and obj.item:
                        obj.item.pick_up()
                        break
            if user_input.keychar == 'i':
                # show the inventory, if an item is selected, use it
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.use()
            if user_input.keychar == 'x':
                chosen_item = inventory_menu('Press the key next to an item to' +
                                             ' drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()
            if user_input.keychar == '.':
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()
            if user_input.keychar == 'c':
                check_level_up()
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Character Information\n Level: ' + str(player.level) + "\n Experience: " +
                       str(player.fighter.xp) + '\n Experience to level up: ' + str(level_up_xp) + '\n Maximum HP: ' +
                       str(player.fighter.max_hp) + '\n Attack: ' + str(player.fighter.power) + '\n Defense: ' +
                       str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)

def next_level():
    global dungeon_level

    message('You take a moment rest, and recover your strength.', colors.light_violet)
    player.fighter.heal(player.fighter.max_hp // 2)

    message('After a rare moment of peace, you descend deeper into the heart of the dungeon...', colors.red)
    dungeon_level += 1
    make_map()
    initialize_fov()

def player_death(player):
    # the game ended!
    global game_state
    message('You died!', colors.red)
    game_state = 'dead'

    # for added effect, transform the player into a corpse!
    player.char = '%'
    player.color = colors.dark_red

def health_color(monster):
    monster.color = colors.light_red
    message(monster.name.capitalize() + ' is weak! Keep fighting!')

def monster_death(monster):
    # transform it into a nasty corpse! it doesn't block, can't be
    # attacked and doesn't move
    message(monster.name.capitalize() + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.', colors.orange)
    monster.char = '%'
    monster.color = colors.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()


def menu(header, options, width):
    if len(options) > 26: raise ValueError('cannot have a menu with more than 26 options.')

    header_wrapped = textwrap.wrap(header, width)
    header_height = len(header_wrapped)
    height = len(options) + header_height

    window = tdl.Console(width, height)

    window.draw_rect(0, 0, width, height, None, fg=colors.white, bg=None)
    for i, line in enumerate(header_wrapped):
        window.draw_str(0, 0+i, header_wrapped[i])

    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        window.draw_str(0, y, text, bg=None)
        y += 1
        letter_index += 1

    x = SCREEN_WIDTH//2 - width//2
    y = SCREEN_HEIGHT//2 - height//2
    root.blit(window, x, y, width, height, 0, 0)

    tdl.flush()
    key = tdl.event.key_wait()
    key_char = key.char
    if key_char == '':
        key_char = ' '

    # convert to ASCII  code to an index; if it corresponds to an option, return it
    index = ord(key_char) - ord('a')
    if index >= 0 and index < len(options):
        return index
    return None

def inventory_menu(header):
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = [item.name for item in inventory]

    index = menu(header, options, INVENTORY_WIDTH)

    if index is None or len(inventory) == 0: return None
    return inventory[index].item

def save_game():
    global object, dungeon_level
    import shelve
    # open a new empty shelve (possibly overwriting old one) to write the game data
    file = shelve.open('savegame', 'n')
    file['map'] = my_map
    file['objects'] = objects
    file['player_index'] = objects.index(player) # index of player objects in list
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['stairs_index'] = objects.index(stairs)
    file['dungeon_level'] = dungeon_level
    file.close()
    
def new_game():
    global player, inventory, game_msgs, game_state, fighter_component, dungeon_level, xp

    # create player
    fighter_component = Fighter(hp=30, defense=2, power=5, xp=0, death_function=player_death)
    player = GameObject(0, 0, '@', 'player', colors.white, blocks=True, fighter=fighter_component)

    player.level = 1

    dungeon_level = 1

    make_map()

    initialize_fov()

    game_state = 'playing'
    inventory = []

    game_msgs = []

    message('Welcome traveler, prepare to get rekt in the Dungeons of Gemma!', colors.red)

def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True

    con.clear()

def play_game():
    global key, mouse, object, turnCount

    player_action = None

    key = tdl.event.get()
    while not tdl.event.is_window_closed():
        # tdl.sys_check_for_event(tdl.EVENT_KEY_PRESS|tdl.EVENT_MOUSE, key.mouse)
        tdl.event.get()
        render_all()
        tdl.flush()

        for object in objects:
            object.clear()

        turnCount = 0
        turnCount+=1
        player_action = handle = handle_keys()
        if player_action == 'exit':
            save_game()
            break

        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.ai:
                    object.ai.take_turn()

def main_menu():

    """
    img = tdl.blit('menu_background.png')

    tdl.console_set_default_foreground(0, tdl.light_yellow)
    """
    panel.draw_str(SCREEN_WIDTH//2, PANEL_HEIGHT//2-4, 'A TEAM OF CRAWL', bg=None)
    panel.draw_str(SCREEN_WIDTH//2, PANEL_HEIGHT-2, 'A Team Of People', bg=None)

    while not tdl.event.is_window_closed():
        # tdl.image_blit_2x(img, 0, 0, 0)

        choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)

        if choice == 0:
            new_game()
            play_game()
        elif choice == 1:
            try:
                load_game()
            except:
                msgbox('\n No saved game to load. \n', 24)
                continue
            play_game()

        elif choice == 2:
            break

def load_game():
    import shelve
    global my_map, objects, player, inventory, game_msgs, game_state, object, stairs, dungeon_level

    file = shelve.open('savegame', 'r')
    my_map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    dungeon_level = file['dungeon_level']
    file.close()

    initialize_fov()

def msgbox(text, width=50):
    menu(text, [], width)

def check_level_up():
    global level_up_xp
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', colors.yellow)

        choice = None
        while choice == None:
            choice = menu('Level up! Choose a stat to raise:\n',
                          ['\nConstitution (+20 HP, from ' + str(player.fighter.max_hp) + ')',
                           '\nStrength (+1 attack, from ' + str(player.fighter.power) + ')',
                           '\nAgility (+1 defense, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)

        if choice == 0:
            player.fighter.max_hp += 20
            player.fighter.hp += 20
        elif choice == 1:
            player.fighter.power += 1
        elif choice == 2:
            player.figther.defense +=1

#############################################
# Initialization & Main Loop                #
#############################################

tdl.set_font('terminal16x16_gs_ro.png', greyscale=True, altLayout=False)
root = tdl.init(SCREEN_WIDTH, SCREEN_HEIGHT, title="Dungeons of Gemma", fullscreen=False)
tdl.setFPS(LIMIT_FPS)
con = tdl.Console(MAP_WIDTH, MAP_HEIGHT)
panel = tdl.Console(SCREEN_WIDTH, PANEL_HEIGHT)

# create object representing the player
fighter_component = Fighter(hp=30, defense=2, power=5, xp=0, death_function=player_death)
player = GameObject(0, 0, '@', 'player', colors.white, blocks=True, fighter=fighter_component)
mouse_coord = (0, 0)
tdl.setFPS(LIMIT_FPS)

fov_recompute = True
objects = [player]

main_menu()



