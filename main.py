import simplejson

__autor__ = 'nickbortolotti'
__licencia__ = 'Apache 2.0'

# Main
import os
import sys
import cgi
import jinja2
import webapp2
import httplib2


# Alternative
import logging

from apiclient.discovery import build
from oauth2client.appengine import OAuth2DecoratorFromClientSecrets
from oauth2client.appengine import AppAssertionCredentials
from google.appengine.api import memcache

# Decorador para el cliente de BigQuery - ** Recuerde utilizar su client_secrets.json **
decorator = OAuth2DecoratorFromClientSecrets(os.path.join(os.path.dirname(__file__), 'client_secrets.json'),
                                             scope='https://www.googleapis.com/auth/plus.me')

#Construccion del servicio de GooglePlus
servicio = build('plus', 'v1')

#Variables del proyecto
proyecto = 'project'

#Entorno Jinja para trabajar plantillas y el HTML
Entorno_Jinja = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

# Global variables Prediction
archivo = "stop_social_offence/prediction_file"
nombre_modelo = "prediction_model"
api_key = "api_key"

# Set up the Prediction API service
credentials = AppAssertionCredentials(scope='https://www.googleapis.com/auth/prediction')
http = credentials.authorize(httplib2.Http(memcache))
service = build("prediction", "v1.6", http=http, developerKey=api_key)
#service = build('prediction', 'v1.6')


class EntrenarModelo(webapp2.RequestHandler):
    def get(self):
        # Entrenar el modelo
        self.response.out.write('Entrenando el Modelo. Esto puede tardar algunos minutos en completarse.')
        payload = {'project': proyecto, 'id': nombre_modelo, 'storageDataLocation': archivo}
        service.trainedmodels().insert(body=payload).execute()


class ValidarModelo(webapp2.RequestHandler):
    def get(self):
        # Validar el modelo a entrenar
        self.response.out.write('Validando el estado del modelo.<br>')
        status = service.trainedmodels().get(project=proyecto, id=nombre_modelo).execute()
        self.response.out.write('Status: ' + status['trainingStatus'])

def DetectarOfensa(message):
    #Regresa el resultado de la prediccion
    body = {'input': {'csvInstance': [message]}}
    output = service.trainedmodels().predict(body=body, project=proyecto, id=nombre_modelo).execute()
    logging.info(output)
    prediction = output['outputLabel']
    if cgi.escape(prediction) == "nothing":					  
        return True
    else:
	    return False

class Panel(webapp2.RequestHandler):
    @decorator.oauth_required
    def get(self):
        http = decorator.http()
        try:
            #lectura de informacion del usuario social
            usuario = servicio.people().get(userId='me').execute(http=http)
            nombre = usuario['displayName']

            #lectura de informacion para las actividades
            actividades = servicio.activities().list(userId='me', collection='public', maxResults='3') \
                .execute(http=http)
            #logging.info(actividades)

            analisis = {}
            for r in actividades['items']:
                analisis.update({r['title']:DetectarOfensa(r['title'])}) #llamada a Prediction

            #Definicion de los datos para insertar en HTML. Jinja2
            plantilla_values = {
                'nombre_usuario': nombre,
                'analisis': analisis,
            }

            #Inferencia de la plantilla con el HTML correspondiente
            template = Entorno_Jinja.get_template('jqueryUI/index_002.html')
            self.response.write(template.render(plantilla_values))

        except:
            e = str(sys.exc_info()[0]).replace('&', '&amp;'
            ).replace('"', '&quot;'
            ).replace("'", '&#39;'
            ).replace(">", '&gt;'
            ).replace("<", '&lt;')
            self.response.out.write("<p>Error: %s</p>" % e)


application = webapp2.WSGIApplication([
            ('/', Panel),
                ('/checkmodel', ValidarModelo),
            (decorator.callback_path, decorator.callback_handler()), ], debug=True)
