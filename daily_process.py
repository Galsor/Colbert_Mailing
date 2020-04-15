from MLP_daily_predictor import MLPModel
from alpha_vantage_api import get_data
from mail_server import MailServer
import datetime

MAIL = MailServer()

def notify_by_mail():
    mess = "This is a test email. Please do not answer it. \n Test UTF-8 : é!°$ù#@ç"
    message = MAIL.create_message("me", "meilliez.antoine@gmail.com", "Test mail from Colbert n°1", mess)
    res = MAIL.send_message("me", message)
    print(res)


def main():
    today = datetime.date.today()
    if today.weekday() not in [5,6]:
	    symbols = ['aapl', 'air.pa', 'ca.pa']
	    finta_param = 14
	    predictions = {}
	    for s in symbols:
	        #get data
	        df, _ = get_data(s, mode='daily', outputsize='compact')
	        #return matrix
	        df = df.iloc[::-1]
	        #get only needed data
	        df = df.iloc[-finta_param:]
	        df = df.rename(columns={c: c[3:] for c in list(df)}).reset_index()
	        model = MLPModel(s, finta_param)
	        pred = model.predict(df)
	        predictions[s]=pred
	    mail = MailServer()
	    mail.send_predictions(predictions)

if __name__ == '__main__':
    main()