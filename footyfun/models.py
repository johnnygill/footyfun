#!/usr/bin/env python

from django.db import models
from django.contrib import admin
from django.forms import ModelForm

NAME_STRING = 100
LONG_STRING = 1000
URL_STRING = 1000

class Competition(models.Model):
    """ Identifier for a competition.

    Examples: Premier League, World Cup etc.
    """
    name = models.CharField(max_length=NAME_STRING)
    date = models.DateField()
    url = models.CharField(max_length=URL_STRING)

    def __str__(self):

        return self.name

class League(models.Model):
    """ A league is used for each set of individuals playing in a competition.

    Eg for World Cup 2014 there might be work and friends leagues etc.
    """
    competition = models.ForeignKey(Competition)
    name = models.CharField(NAME_STRING)
    date = models.DateField()
    start = models.DateField()
    end = models.DateField()

    def __str__(self):

        return self.name
    
class Game(models.Model):
    """ Details of a game for some competition. """
    competition = models.ForeignKey(Competition)
    teama = models.CharField(max_length=NAME_STRING)
    teamb = models.CharField(max_length=NAME_STRING)
    ascore = models.IntegerField(default=-1)
    bscore = models.IntegerField(default=-1)
    matchtime = models.DateTimeField()
    detail = models.CharField(max_length=LONG_STRING)

    def __str__(self):

        return '%s v %s %s %s' % (
            self.teama, self.teamb,
            self.competition.name, str(self.matchtime))

class Competitor(models.Model):
    """ Keep track of who is entered in each league """
    punter = models.UserField(required=True)
    nickname = models.CharField()
    league = models.ForeignKey(League)
    entered = models.BooleanField()

    def __str__(self):
        """ Pretty print a Competitor """
        return '%s %s %s %s' % (self.nickname,
                                str(self.punter),
                                self.league.name,
                                str(self.entered))

class Prediction(models.Model):
    """ A prediction from a punter in one of the leagues """
    league = models.ForeignKey(League)
    game = models.ForeignKey(Game)
    competitor = models.ForeignKey(Competitor)
    punter = models.UserField(required=True)
    ascore = models.IntegerField(default=-1)
    bscore = models.IntegerField(default=-1)

    def __str__(self):
        """ Pretty print a prediction """
        return '%s %s %d %d' % (str(self.game),
                                str(self.competitor),
                                self.ascore, self.bscore)
                                
    
class Comment(models.Model):

    subject = models.CharField()
    content = models.CharField(multiline=True)
    date = models.DateTimeField(auto_now_add=True)
    competitor = models.ForeignKey(Competitor)
    league = models.ForeignKey(League)


class PointInfo(models.Model):

    date = models.DateField()
    competitor = models.ForeignKey(Competitor)
    league = models.ForeignKey(League)
    perfect = models.FloatField(default=0.)
    goal_difference = models.FloatField(default=0.)
    goals = models.FloatField(default=0.)
    result = models.FloatField(default=0.)
    count = models.FloatField(default=0.)

    totals = models.BooleanField(default=False)

    def __str__(self):

        return '%s %s %5.0f %5.0f %5.0f %5.0f %5.0f %s' % (
            str(self.date), str(self.totals),
            self.count, self.perfect, self.goals,
            self.goal_difference, self.result, self.competitor.nickname)


    def reset(self):

        self.perfect = 0.
        self.goal_difference = 0.
        self.goals = 0.
        self.result = 0.
        self.count = 0.

    def add(self, points):

        self.perfect += points.perfect
        self.goal_difference += points.goal_difference
        self.goals += points.goals
        self.result += points.result
        self.count += points.count

    def subtract(self, points):

        self.perfect -= points.perfect
        self.goal_difference -= points.goal_difference
        self.goals -= points.goals
        self.result -= points.result
        self.count -= points.count

    def initialise(self, points):

        self.perfect = points.perfect
        self.goal_difference = points.goal_difference
        self.goals = points.goals
        self.result = points.result
        self.count = points.count

    def to_points(self):

        points = Points(self.league.competition.name)
        points.initialise(self)
        points.set_total()
        return points

class Statto(object):

    def __init__(self, league):
        
        self.league = league

    def update_points(self, day, out=None):
        """ Update points totals for day. """

        games = []
        for game in self._days_games(day):
            if game.ascore >= 0:
                games.append(game)
    
        league = self.league
        if out is not None:
            out.write('<br>xxx')
            out.write(str(len(games)))

        competitors = dict([(x.nickname, x) for x in league.competitor_set])

        # get points for the day
        points, junk = process_predictions(games, league, False, out=out)

        # retrieve current stuff
        pointinfo = PointInfo.all().filter('date =', day).filter('league =', league).filter('totals =', False)

        # convert to a dictionary
        current = {}
        for info in pointinfo:
            who = info.competitor.nickname
            if who in current:
                info.delete()
            else:
                current[info.competitor.nickname] = info


        # Now convert Points into PointInfo
        for who, point in points.iteritems():
            pinfo = current.get(who)
            if pinfo is None:
                pinfo = PointInfo()
                pinfo.league = league
                pinfo.competitor = competitors[who]
                pinfo.date = day
            else:
                pinfo.reset()
            pinfo.add(point)
            pinfo.save()

        # finally delete any poininfo no longer needed
        for pinfo in pointinfo:
            who = pinfo.competitor.nickname
            if who not in points:
                pinfo.delete()

    def cummulate(self, end=None):
        """ Create cumulative totals for each day up to end """
        current = self.league.date

        if current >= end: return

        # get totals for current
        pointinfo = PointInfo.all().filter('date =', current).filter('league =', self.league).filter('totals =', True)
        totals = {}
        for info in pointinfo:
            totals[info.competitor.nickname] = info
            
        next = timedelta(days=1)
        while current < end:
            # move on to next
            current += next

            # get points for current
            pointinfo = PointInfo.all().filter('date =', current).filter('league =', self.league).filter('totals =', False)

            # turn points into a dictionary
            pinfo = dict([(t.competitor.nickname, t) for t in pointinfo])

            # remove existing totals
            for info in PointInfo.all().filter('date =', current).filter('league =', self.league).filter('totals =', True):
                info.delete()

            # now need the set of nicks in totals and pointinfo
            entered = set(totals.keys() + pinfo.keys())

            for who in entered:
                total = totals.get(who)
                if total is None:
                    total = PointInfo()
                    total.league = self.league
                    total.competitor = pinfo[who].competitor
                    total.totals = True
                    total.date = current
                    totals[who] = total

                points = pinfo.get(who)
                if points is not None:
                    total.add(points)

            # save the records
            for total in totals.itervalues():

                info = PointInfo()
                info.league = total.league
                info.competitor = total.competitor
                info.date = current
                info.totals = True

                info.initialise(total)
                info.save()

        # update date
        self.league.date = end
        self.league.save()
        

    def stats(self, start=None, end=None):
        """ Get table stats from start to end """
        if end is None:
            end = date.today()

        self.cummulate(end)

        spoints = []
        if start is not None:
            spoints = PointInfo.all().filter('date =', start).filter('league =', self.league).filter('totals =', True)

        startinfo = {}
        for sp in spoints:
            startinfo[sp.competitor.nickname] = sp
        
        epoints = PointInfo.all().filter('date =', end).filter('league =', self.league).filter('totals =', True)

        results = []
        for endinfo in epoints:
            who = endinfo.competitor.nickname
            if who in startinfo:
                endinfo.subtract(startinfo[who])
            results.append(endinfo)

        return results
        
    def _days_games(self, day):

        tday = datetime.fromordinal(day.toordinal())
        tnextday = tday + timedelta(days=1)
        
        return Game.all().filter('matchtime >=', tday).filter('matchtime <=', tnextday)
        

class MainPage(webapp.RequestHandler):
    def get(self):

        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            path = os.path.join(os.path.dirname(__file__), 'templates/game_list.html')
            self.response.out.write(template.render(path, {}))


class NickNameField(forms.CharField):
    pass
            
class LeagueIdField(forms.CharField):

    def clean(self, value):

        result = forms.CharField.clean(self, value)

        try:
            league = League.get(result)
        except datastore_errors.BadKeyError:
            raise forms.ValidationError('Unknown League')
        
        return result
            
class RegisterForm(forms.Form):
    """ Form to register for a league """
    league_id = LeagueIdField(required=True)
    nick_name = NickNameField(required=True)

        
class WelcomePage(webapp.RequestHandler):
    def get(self):

        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            leagues = Competitor.all().filter('punter =', user).filter('entered =', True)
            leagues = [x.league for x in leagues if x.league.end >= date.today()]
            admin = users.is_current_user_admin()
            path = os.path.join(os.path.dirname(__file__), 'templates/welcome.html')
            self.response.out.write(template.render(
                    path, dict(leagues=leagues, register=RegisterForm(), admin=admin)))

    def post(self):

        form = RegisterForm(self.request.POST)

        if form.is_valid():
            # Register the user
            user = users.get_current_user()
            if not user:
                self.redirect(users.create_login_url(self.request.uri))
            else:
                clean = form.clean()
                league = League.get(clean['league_id'])

                # Check not already entered
                entered = set([x.punter.email() for x in league.competitor_set])
                if user.email() in entered:
                    self.response.out.write('You are already entered in this league')
                    return

                # Check nickname not already taken
                nicknames = set([x.nickname for x in league.competitor_set])
                nickname = clean['nick_name']
                if nickname in nicknames:
                    self.response.out.write('%s has already been taken as a nickname in this league')
                    return
                
                
                competitor = Competitor(punter=user)
                competitor.nickname = nickname
                competitor.entered = True
                competitor.league = league
                competitor.put()
                self.redirect('/leagueview/?league=%d' % league.key().id())
                return
        else:
            path = os.path.join(os.path.dirname(__file__), 'templates/welcome.html')
            self.response.out.write(template.render(
                    path, dict(register=form)))
            

class CommentForm(djangoforms.ModelForm):
    class Meta:
        model = Comment
        exclude = ['competitor', 'league']

class LeaguePage(webapp.RequestHandler):

    def get(self):

        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            league_id = int(self.request.get('league'))
            league = League.get_by_id(league_id)

            # Check user is entered
            competitor = get_competitor(league, user)
            if not competitor:
                self.response.out.write('You are not a member of this league')
                return
           
            games = league.competition.game_set.order('matchtime')

            preds = get_prediction_lookup(competitor, league)

            ngames = []
            for game in games:
                pred = preds.get(game.key())
                    
                if pred is not None and pred.ascore >= 0:
                    game.preda = pred.ascore
                    game.premodels = pred.bscore

                ngames.append(game)
            
            comments = league.comment_set.order('date')

            comment_form = CommentForm()

            path = get_template(league, 'game_list.html')
            self.response.out.write(template.render(path, dict(games=ngames,
                                                               npreds=len(preds),
                                                               competition=league.competition,
                                                               comment_form = comment_form,
                                                               comments=comments,
                                                               league=league)))

class PostCommentPage(webapp.RequestHandler):

    def post(self):

        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            form = CommentForm(self.request.POST)
            if form.is_valid():
                clean = form.clean()
                
                comment = Comment()
                league_id = int(self.request.get('league'))
                league = League.get_by_id(league_id)

                competitor = league.competitor_set.filter('punter =', user)
                if not competitor:
                    self.response.out.write('You are already entered in this league')
                    return
                
                comment.competitor = competitor[0]
                comment.league = league
                comment.content = clean['content']
                comment.subject = clean['subject']
                comment.date = datetime.now()
                comment.put()
        
        self.redirect('/leagueview/?league=%d' % league_id)


def get_now():
    """ Return now.

    Try to deal with timezone fun.

    For now, assume we are in IST.

    Really need to fix so we cope with switch to UTC in winter.
    """
    uk = pytz.timezone('Europe/London')
    return datetime.now(uk).replace(tzinfo=None)

        
def get_prediction_lookup(competitor, league):
    
    # Get any predictions for this competitor
    predictions = Prediction.all()
    predictions.filter('competitor =', competitor)
    predictions.filter('league =', league)

    # Turn into lookup table
    lookup = {}
    for prediction in predictions:
        lookup[prediction.game.key()] = prediction

    return lookup

class PredictForm(djangoforms.ModelForm):
    class Meta:
        model = Game
        exclude = ['competition']

def get_competitor(league, user):
    """ Retuern whether user is entered in the league """
    competitors = league.competitor_set.filter('punter =', user)
    if competitors.count() == 0:
        return False

    return competitors[0]

def get_template(league, base):
    """ Return template for this league """
    
    lname = league.name.replace(' ', '_')
    cname = league.competition.name.replace(' ', '_')
    paths = [
        os.path.join(os.path.dirname(__file__), 'templates', cname, lname, base),
        os.path.join(os.path.dirname(__file__), 'templates', cname, base),
        os.path.join(os.path.dirname(__file__), 'templates', base),]

    for path in paths:
        if os.path.exists(path):
            return path

    return base

class PredictPage(webapp.RequestHandler):

    def get(self):

        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        else:

            league = League.get_by_id(int(self.request.get('league')))

            if league is None:
                self.response.out.write("You are not entered in this league")
                return

            # Check user is entered in the league
            competitor = get_competitor(league, user)
            if not competitor:
                self.response.out.write("You are not entered in this league")
                return
           
            days = self.request.get('days')
            games = league.competition.game_set.order('matchtime')
            start = get_now()
            games.filter('matchtime >', start)

            if days:
                end = start + timedelta(days=int(days))
                games.filter('matchtime <=', end)

            # Get user's predictions for this league
            predictions = get_prediction_lookup(competitor, league)
            fixgames = []
            for game in games:
                if game.key() in predictions:
                    pred = predictions[game.key()]
                    game.ascore = pred.ascore
                    game.bscore = pred.bscore
                else:
                    game.ascore = game.bscore = 0
                fixgames.append(game)

            games = fixgames

            path = get_template(league, 'predictions.html')
            self.response.out.write(template.render(path, dict(
                        games=games,
                        league=league)))


    def post(self):

        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            #self.response.out.write(str(self.request.POST))
            ascores = self.request.get('ascore', allow_multiple=True)
            bscores = self.request.get('bscore', allow_multiple=True)
            games = self.request.get('game', allow_multiple=True)
            league = League.get(self.request.get('league'))

            competitor = get_competitor(league, user)
            if not competitor:
                self.response.out.write("You are not entered in this league")
                return
            
            current = get_prediction_lookup(competitor, league)

            now = get_now()
            
            for ascore, bscore, game in zip(ascores, bscores, games):
                #self.response.out.write('%s %s x%sx\n' % (ascore, bscore, game))
                game = Game.get(game)

                if game.matchtime < now: continue

                if game.key() in current:
                    record = current[game.key()]
                else:
                    record = Prediction(competitor=competitor, punter=user)
                    record.game = game
                    record.league = league
               

                record.ascore = int(ascore)
                record.bscore = int(bscore)

                record.put()

            self.redirect('/leagueview/?league=%d' % league.key().id())
        


class TablePage(webapp.RequestHandler):
    """ Return current prediction league table. """

    def get(self):

        league = League.get_by_id(int(self.request.get('league')))

        path = get_template(league, 'table.html')

        results = create_table(league)
    
        self.response.out.write(template.render(path, results))


class FastTablePage(webapp.RequestHandler):
    """ Return current prediction league table. """

    def get(self):

        league = League.get_by_id(int(self.request.get('league')))
        start = self.request.get('start')
        if start:
            start = parse_date(start)

        end = parse_date(self.request.get('end', None)).date()

        path = get_template(league, 'table.html')

        statto = Statto(league)

        pinfo = statto.stats(start, end)

        scores = []
        for info in pinfo:
            punter = info.competitor.nickname
            points = info.to_points()

            scores.append(dict(
                    total=points.total,
                    sort=(points.total,points.perfect,points.goal_difference,points.goals,punter),
                    points=points,
                    nickname=punter,
                    ))

        results = dict(scores=scores,
                       details=[],
                       league=league)

        self.response.out.write(template.render(path, results))


class MotmPage(webapp.RequestHandler):
    """ Return current prediction league table. """

    def get(self):

        league = League.get_by_id(int(self.request.get('league')))
        count = int(self.request.get('count', 2))


        start = self.request.get('start')
        if start:
            start = parse_date(start).date()
        else:
            start = league.start
            

        final = self.request.get('end')
        if final:
            final = parse_date(final).date()
        else:
            final = date.today()
        end = next_month_start(start)

        # Get dates to show
        dates = []
        while start < final:
            dates.append((start, end))
            start = end
            end = next_month_start(end)


        # Reverse the dates
        dates.reverse()

        statto = Statto(league)
        months = []

        oneoff = timedelta(days=-1)
        for start, end in dates[:count]:
            
            pinfo = statto.stats(start+oneoff, end+oneoff)
            scores = []
            for info in pinfo:
                punter = info.competitor.nickname
                points = info.to_points()

                if points.count > 0:
                    scores.append(dict(
                        total=points.total,
                        sort=(points.total,points.perfect,points.goal_difference,points.goals,punter),
                        points=points,
                        nickname=punter,
                        ))

            if scores:
                months.append(dict(scores=scores, month=start))

        results = dict(league=league, months=months, dates=dates[count:])

        path = get_template(league, 'motm.html')
        self.response.out.write(template.render(path, results))

        
def next_month_start(now):
    
    add31 = timedelta(days=31)
    month = now + add31
    return date(month.year, month.month, 1)
    

class WeeklyTablePage(webapp.RequestHandler):
    """ Show this week's table.
    """
    def get(self):

        end = get_now()
        start = end - timedelta(days=7)

        league = League.get_by_id(int(self.request.get('league')))

        results = create_table(league, start, end)
        path = get_template(league, 'table.html')
        self.response.out.write(template.render(path, results))


def create_table(league, start=None, end=None):
    """ Do grunt work to create our league table. """

    tymes = []
    tymes.append(time.time())
    if start is None:
        start = datetime(2000,1,1)
    if end is None:
        end = get_now()

    
    games = league.competition.game_set.filter('matchtime >=', start).filter('matchtime <=', end)
    tymes.append(time.time())
    
    results = []
    for game in games:
        if game.ascore >= 0:
            results.append(game)

    tymes.append(time.time())

    cname = league.competition.name
    scores, details = process_predictions(results, league)

    tymes.append(time.time())

    results = []
    for punter, points in scores.iteritems():

        points.set_total()
        results.append(dict(
                total=points.total,
                sort=(points.total,points.perfect,points.goal_difference,points.goals,punter),
                points=points,
                nickname=punter,
                ))

    tymes.append(time.time())
    timings = []
    for a, b in zip(tymes[0:-1], tymes[1:]):
        timings.append(b-a)
    
    return dict(scores=results,
                details=details,
                times=timings,
                league=league)


def process_predictions(results, league, do_details=True, out=None):
    
    scores = {}
    details = []
    quantum = 1.0

    cname = league.competition.name

    for result in results:

        predictions = result.prediction_set.filter('league =', league)
    
        for prediction in predictions:
            if out is not None:
                out.write('<br>pred ')
                out.write(str(prediction))
                out.write('<br>')
                
            points = scores.setdefault(prediction.competitor.nickname, Points(cname))
            points.update(prediction, result, quantum)

            if not do_details:
                continue

            points = Points(cname)
            points.update(prediction, result, quantum)
            points.set_total()
            details.append(dict(points=points,
                                game=result, game_id=result.key().id,
                                preda=prediction.ascore,
                                premodels=prediction.bscore,
                                punter=prediction.competitor.nickname,
                                total=points.total,
                                matchtime=result.matchtime))

    return scores, details

class FootyPoints(object):
    def __init__(self):

        self.perfect = 0
        self.goal_difference = 0
        self.goals = 0
        self.result = 0
        self.count = 0

    def initialise(self, points):
        
        self.perfect = points.perfect
        self.goal_difference = points.goal_difference
        self.goals = points.goals
        self.result = points.result
        self.count = points.count
        
    def set_total(self):
        
        self.total = self.goals + self.goal_difference + self.perfect + self.result
        if self.count > 0:
            self.ppp = self.total / float(self.count)

    def calculate_averages(self):

        self.set_total()
        count = float(self.count)

        return dict(count =count,
                    goals = self.goals / count,
                    goal_difference = self.goal_difference / count,
                    perfect = self.perfect / count,
                    result = self.result / count,
                    total = self.total / count)

    def update(self, prediction, result, quantum=1.0):

        self.count += 1

        pascore, pbscore = prediction.ascore, prediction.bscore
        ascore, bscore = result.ascore, result.bscore

        # Either teams goals right
        if pascore == ascore:
            self.goals += quantum

        if pbscore == bscore:
            self.goals += quantum

        # Goal difference
        if (pbscore - pascore ==
            bscore - ascore):
            self.goal_difference += quantum

        # Perfect score
        if (pascore == ascore and 
            pbscore == bscore):
            self.perfect += quantum

        # Same result
        if ((pascore > pbscore  and
             ascore > bscore) or

            (pascore < pbscore  and
             ascore < bscore) or

            (pascore == pbscore  and
             ascore == bscore)):

            self.result += 2 * quantum

class EggPoints(FootyPoints):
    """ Points class for egg-chasing.

    Scores are higher so harder to predict so we need a different update method.
    """
    tolerance = 3
    
    def update(self, prediction, result, quantum=1.0):

        self.count += 1
        tolerance = self.tolerance
        tolerance1 = self.tolerance + 1
        
        # Either teams points close
        delta = abs(prediction.ascore - result.ascore)
        if delta <= tolerance:
            self.goals += quantum * (tolerance1 - delta)

        delta = abs(prediction.bscore - result.bscore)
        if delta <= tolerance:
            self.goals += quantum * (tolerance1 - delta)

        # Point difference close
        delta = abs((prediction.bscore - prediction.ascore) -
                   (result.bscore - result.ascore))
        if delta <= tolerance:
            self.goal_difference += quantum * (tolerance1 - delta)

        # Both points close
        delta = (abs(prediction.ascore - result.ascore) +
                 abs(prediction.bscore - result.bscore))
        if delta <= tolerance:
            self.perfect += quantum  * (tolerance1 - delta)

        # Same result
        if ((prediction.ascore > prediction.bscore  and
             result.ascore > result.bscore) or

            (prediction.ascore < prediction.bscore  and
             result.ascore < result.bscore) or

            (prediction.ascore == prediction.bscore  and
             result.ascore == result.bscore)):

            self.result += 2 * quantum
    
def Points(competition):
    """ Return an appropriate points object for the competition.

    Break my naming convention and make it look like a class.
    """
    if 'egg' in competition:
        return EggPoints()

    return FootyPoints()


class GamePage(webapp.RequestHandler):
    """ Page for a single game """

    def get(self):
        """ Return current prediction league table for a game. """

        # User check
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        league = League.get_by_id(int(self.request.get('league')))

        if league is None:
            # no such league, tell them they aren't entered.
            self.response.out.write("You are not entered in this league")
            return

        # Check user is entered in the league
        competitor = get_competitor(league, user)

        # Get the game we are interested in
        game = Game.get_by_id(int(self.request.get('game')))

        # Get all predictions for the game
        predictions = game.prediction_set.filter('league =', league)
        
        now = get_now()
        if game.matchtime > now:
            path = get_template(league, 'comebacklater.html')
            self.response.out.write(template.render(path, dict(
                        league=league,
                        fixture='%s v %s' % (game.teama, game.teamb))))
            return

        details = []
        quantum = 1.0
        for prediction in predictions:
                                        
            points = Points(league.competition.name)
            points.update(prediction, game, quantum)
            points.set_total()
            nickname = prediction.competitor.nickname
            details.append(dict(points=points,
                                game=game,
                                preda=prediction.ascore,
                                premodels=prediction.bscore,
                                punter=nickname,
                                total=points.total, 
                                sort=(points.total, nickname),
                                ))

        path = get_template(league, 'game.html')
        self.response.out.write(template.render(path, dict(
                    league=league,
                    fixture='%s %d %d %s' % (game.teama, game.ascore, game.bscore, game.teamb),
                    details=details))) 

class TodayPage(webapp.RequestHandler):

    def get(self):
        """ Handle get requests. """

        # User check
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        games = todays_games()
        league = self.request.get('league')

        self.response.out.write(
            template.render("templates/today.html",
                            dict(games=games, league=league)))
    
def todays_games():

    today = date.today()
    today = datetime.fromordinal(today.toordinal())
    tomorrow = today + timedelta(days=1)

    return Game.all().filter('matchtime >=', today).filter('matchtime <=', tomorrow)

        
class DebugPage(webapp.RequestHandler):
    """ Page to dump out arbitrary stuff for debugging """

    def get(self):
        """ Get some stuff. """
        today = date.today()
        today = datetime.fromordinal(today.toordinal())
        yesterday = today - timedelta(days=1)

        #games = Game.all().filter('teama =', 'Germany').filter('teamb =', 'Spain').filter('matchtime >=', yesterday)

        games = [Game.get_by_id(84)]
        #self.response.out.write('Number of games %d' % games.count())
        for game in games:
            for pred in game.prediction_set:
                self.response.out.write('<p> %s %d %s %s %d %d %s' % (
                        pred.key(), pred.key().id(), game.teama, game.teamb,
                        pred.ascore, pred.bscore,
                        pred.competitor.nickname))
                                    
            
def parse_date(date=None, default=None):

    if date is None:
        if default is None:
            default = datetime.today()
        return default

    year, month, day = [int(x) for x in date.split('-')]
    return datetime(year=year, month=month, day=day)
    
 
        
application = webapp.WSGIApplication([
  ('/', WelcomePage),
  ('/league/.*', MainPage),
  ('/leagueview/.*', LeaguePage),
  ('/predictview/.*', PredictPage),
  ('/table/.*', FastTablePage),
  ('/motm/.*', MotmPage),
  ('/slowtable/.*', TablePage),
  ('/weeklytable/.*', WeeklyTablePage),
  ('/game/.*', GamePage),
  ('/today/.*', TodayPage),
  ('/post_comment/.*', PostCommentPage),
  ('/debug/.*', DebugPage),
  
], debug=True)


def real_main():
    wsgiref.handlers.CGIHandler().run(application)

def profile_main():
    # This is the main function for profiling 
    # We've renamed our original main() above to real_main()
    import cProfile, pstats
    prof = cProfile.Profile()
    prof = prof.runctx("real_main()", globals(), locals())
    print "<pre>"
    stats = pstats.Stats(prof)
    stats.sort_stats("cumulative")  # Or cumulative
    stats.print_stats(80)  # 80 = how many to print
    # The rest is optional.
    # stats.print_callees()
    # stats.print_callers()
    print "</pre>"
 
main = profile_main
main = real_main
    
if __name__ == '__main__':
    main()
