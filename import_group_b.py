import os, json
from supabase import create_client

sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

pipeline = sb.table('pipelines').select('id').eq('is_default', True).execute()
pipeline_id = pipeline.data[0]['id'] if pipeline.data else None

contacts = [
{"fn":"Jeff","ln":"Booker","email":"jeff@greatfloridahomes.com","phone":"954-695-7653","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"4","volume":"1886000"},
{"fn":"Heidi","ln":"Dubree","email":"heididubree@gmail.com","phone":"305-994-4700","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"2","volume":"1135500"},
{"fn":"Mara","ln":"Garcia","email":"marasellsoflo@gmail.com","phone":"786-356-9400","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"4","volume":"1321500"},
{"fn":"Mimi","ln":"Goon","email":"mimisellshouses@gmail.com","phone":"954-510-5924","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"4","volume":"1794557"},
{"fn":"Dennis","ln":"Jackson","email":"acusearch@yahoo.com","phone":"954-803-1950","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"2","volume":"778500"},
{"fn":"Judith","ln":"Jimenez","email":"judithjrealtor@gmail.com","phone":"954-557-4632","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"2","volume":"449418"},
{"fn":"Teka","ln":"Parkinson","email":"tekasellsfl21@hotmail.com","phone":"347-794-3117","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"5","volume":"2523480"},
{"fn":"Juan","ln":"Romeo","email":"carlosromeo1968@gmail.com","phone":"954-593-7475","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"2","volume":"1040000"},
{"fn":"Vincent","ln":"Ruffino","email":"vruffino@comcast.net","phone":"954-448-0054","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"3","volume":"934000"},
{"fn":"Cindie","ln":"Sciortino","email":"cindiesciortino@gmail.com","phone":"954-608-1787","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"4","volume":"2140000"},
{"fn":"Sender","ln":"Seigel","email":"sender@senderslistings.com","phone":"954-998-3261","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"3","volume":"2125300"},
{"fn":"Lola","ln":"Taylor","email":"upakut1@aol.com","phone":"954-818-9140","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"2","volume":"795000"},
{"fn":"Esther","ln":"Zago","email":"estherzvre@gmail.com","phone":"917-842-5163","brokerage":"Keller Williams Realty Consultants","city":"Coral Springs","county":"Broward","deals":"3","volume":"2125300"},
{"fn":"Joseph","ln":"Napolitano","email":"napolitanoj97@gmail.com","phone":"772-812-2722","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"2","volume":"884500"},
{"fn":"Mimoza","ln":"Woodin","email":"mimiwoodin@yahoo.com","phone":"772-618-0152","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"2","volume":"595000"},
{"fn":"Donald","ln":"Baetzold","email":"donald@searchlikeagent.com","phone":"772-919-2100","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"6","volume":"2543175"},
{"fn":"Michael","ln":"Brennan","email":"mike.brennan1410@yahoo.com","phone":"561-315-6344","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"5","volume":"2430000"},
{"fn":"Jodi-Ann","ln":"Brown","email":"jodi@jodisellshomesfl.com","phone":"561-452-1691","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"5","volume":"2326160"},
{"fn":"Diane","ln":"Buchholz","email":"diane.buchholz@att.net","phone":"772-834-0671","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"6","volume":"1965000"},
{"fn":"Jean-Pierre","ln":"Burke","email":"jpburke407@gmail.com","phone":"917-371-2215","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"3","volume":"948500"},
{"fn":"Pauline","ln":"Crain","email":"crain.pauline@gmail.com","phone":"561-452-5560","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"3","volume":"670000"},
{"fn":"Tamara","ln":"Drake","email":"tldrealtor1@gmail.com","phone":"561-319-7027","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"2","volume":"1080000"},
{"fn":"Jay","ln":"Fishbein","email":"abkotrading@yahoo.com","phone":"772-418-4950","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"2","volume":"969000"},
{"fn":"Valinda","ln":"Hanna-Lazarus","email":"realtorvalinda@gmail.com","phone":"772-626-1529","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"4","volume":"1215000"},
{"fn":"Linda","ln":"Humbert","email":"graverlinda@gmail.com","phone":"352-455-4578","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"4","volume":"1295500"},
{"fn":"Joachim","ln":"Leger","email":"joachim1realtor@gmail.com","phone":"772-807-2933","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"4","volume":"1870000"},
{"fn":"Emelyn","ln":"Marcelino","email":"realestatewithemelyn@gmail.com","phone":"561-524-0224","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"3","volume":"924000"},
{"fn":"Albert","ln":"Mcdonald","email":"amcdonaldsellshomes@gmail.com","phone":"305-775-2245","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"2","volume":"647000"},
{"fn":"Karen","ln":"Miret","email":"karenmiret@yahoo.com","phone":"772-873-4115","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"5","volume":"2030250"},
{"fn":"Louis","ln":"Piombino","email":"louispiombino2@gmail.com","phone":"772-233-6642","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"2","volume":"600000"},
{"fn":"Norman","ln":"Platts","email":"parker.platts@aol.com","phone":"772-201-2654","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"2","volume":"1295000"},
{"fn":"April","ln":"Schoen","email":"aakw1224@gmail.com","phone":"772-267-6063","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"4","volume":"1038000"},
{"fn":"Andrew","ln":"Szaniszlo","email":"andyyourrealtor@gmail.com","phone":"772-828-1607","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"5","volume":"2082000"},
{"fn":"Trina","ln":"Wise","email":"trinasellshouses@gmail.com","phone":"772-812-9953","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"4","volume":"1559000"},
{"fn":"Lanishia","ln":"Wyche","email":"lanishiasales@gmail.com","phone":"772-332-1679","brokerage":"Keller Williams Realty Of Psl","city":"Port St. Lucie","county":"St. Lucie","deals":"2","volume":"855500"},
{"fn":"Nadine","ln":"August","email":"nadinesellshomes@gmail.com","phone":"954-646-6103","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"2","volume":"665000"},
{"fn":"Kathleen","ln":"Costanzo","email":"kathleen@marinaandkathleen.com","phone":"954-914-8060","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"6","volume":"1841000"},
{"fn":"Christine","ln":"Goodwin","email":"christisellsflorida@gmail.com","phone":"754-201-5013","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"2","volume":"670000"},
{"fn":"Michelle","ln":"Jacques","email":"mrbj611@gmail.com","phone":"954-873-2114","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"1","volume":"55000"},
{"fn":"Love","ln":"Jones","email":"loveluxurylivingllc@gmail.com","phone":"954-305-2544","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"3","volume":"1280000"},
{"fn":"Adam","ln":"Kapit","email":"ajkapit@gmail.com","phone":"954-665-6545","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"5","volume":"4297500"},
{"fn":"Alissa","ln":"Keiler","email":"alissakeiler.realtor@gmail.com","phone":"954-203-5322","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"1","volume":"81500"},
{"fn":"Alexander","ln":"Kublickis","email":"alexanderkay@msn.com","phone":"954-829-4268","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"3","volume":"3655027"},
{"fn":"Jianna","ln":"Minott","email":"jiannam1@outlook.com","phone":"305-203-9441","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"2","volume":"1022500"},
{"fn":"Dorothy","ln":"Santiago","email":"dorrysantiago@gmail.com","phone":"954-812-0761","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"2","volume":"1650000"},
{"fn":"Marina","ln":"Sarabia","email":"info@marinaandkathleen.com","phone":"954-914-8056","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"5","volume":"1662000"},
{"fn":"Samantha","ln":"Suarez","email":"ssuarez1114@yahoo.com","phone":"678-687-7971","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"2","volume":"1013000"},
{"fn":"Kyle","ln":"Willson","email":"kylewillson.realtor@yahoo.com","phone":"954-552-0748","brokerage":"Keller Williams Realty Professionals","city":"Fort Lauderdale","county":"Broward","deals":"3","volume":"1266500"},
]

imported = 0
errors = 0

for c in contacts:
    name = c['fn'] + ' ' + c['ln']
    try:
        deals = float(c['deals'])
        volume = float(c['volume'])
        avg_price = str(int(volume / deals)) if deals > 0 else ''

        result = sb.table('leads').insert({
            'name': name,
            'first_name': c['fn'],
            'last_name': c['ln'],
            'email': c['email'],
            'phone': c['phone'],
            'source': 'KW Agent List - Broward/STL',
            'current_brokerage': c['brokerage'],
            'brokerage': 'Keller Williams',
            'deals_per_year': c['deals'],
            'avg_price': avg_price,
            'tags': ['group-b', 'kw-gut-punch', 'KW_Broward_STL_1_to_5_units', c['county'].lower()],
            'lead_score': 25,
            'lead_temperature': 'cold',
            'stage': 'new',
            'status': 'new',
            'license_state': 'FL',
        }).execute()

        cid = result.data[0]['id']

        if pipeline_id:
            sb.table('opportunities').insert({
                'contact_id': cid,
                'pipeline_id': pipeline_id,
                'stage': 'new_fb_lead',
                'source': 'KW Agent List - Broward/STL',
                'status': 'open'
            }).execute()

        sb.table('lead_notes').insert({
            'lead_id': cid,
            'author': 'System',
            'content': 'Imported from KW agent list. ' + c['brokerage'] + ', ' + c['city'] + '. Production: ' + c['deals'] + ' deals, $' + '{:,}'.format(int(volume)) + ' volume LTM. A/B Test Group B - Gut Punch variant.'
        }).execute()

        sb.table('lead_activity').insert({
            'lead_id': cid,
            'activity_type': 'created',
            'description': 'Contact imported: ' + name + ' (Group B - Gut Punch test)'
        }).execute()

        imported += 1
    except Exception as e:
        errors += 1
        print('Error: ' + name + ' - ' + str(e))

print('IMPORT COMPLETE')
print('Imported: ' + str(imported))
print('Errors: ' + str(errors))
