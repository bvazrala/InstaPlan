import path from 'node:path';
import {test,expect} from '@playwright/test';
import type {Planner} from '../../lib/types';
const people=['Jordan','Maya','Alex','Sam'].map((name,index)=>({id:['demo-you','demo-maya','demo-alex','demo-sam'][index],name,handle:name.toLowerCase(),hue:40+index*60,avatarUrl:`/planner/people/${name.toLowerCase()}.svg`}));
test('Maps creation, conversation-led RSVP, one animated choice and a clean demo reset',async({page},info)=>{
  let planner:Planner|null=null;
  const messages:{id:string;from:string;text:string;sentAt:string}[]=[];
  const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
  const selectedPlaces:string[]=[];const responses:{going:boolean;demoSpeakerId:string}[]=[];const privateRequests:string[]=[];
  const headers={'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'*'};
  await page.route('https://images.example/venue.jpg',route=>route.fulfill({path:path.join(__dirname,'../assets/widget-venue.png'),contentType:'image/png'}));
  await page.route('**/health',route=>route.fulfill({json:{ok:true,demoMode:true,demoUserId:'demo-you'},headers}));
  await page.route(/\/chats(?:\?|\/|$)|\/trips\//,async route=>{
    const request=route.request(),pathname=new URL(request.url()).pathname,method=request.method();
    if(method==='OPTIONS'){await route.fulfill({status:204,headers});return;}
    const data=['POST','PATCH','PUT'].includes(method)?request.postDataJSON():{};
    let body:unknown=null;
    if(pathname==='/chats')body=[{id:'crew',name:'Weekend crew',group:true,members:people.map(person=>person.id)}];
    else if(pathname.endsWith('/members'))body=people;
    else if(pathname.endsWith('/planner/places'))body=[{id:'austin-city',label:'Austin, TX, USA'},{id:'exact-cafe',label:'Garden Cafe, Austin, TX'}];
    else if(pathname.endsWith('/planners')){
      selectedPlaces.push(data.placeId);
      planner={tripId:'planner-one',title:data.title,topic:data.topic,timezone:data.timezone,revision:0,approvalRevision:0,status:'collecting',simpleFlow:true,
        template:{title:data.title,topic:data.topic,budget:{},when:{flexibility:{},agreed:null},where:{destination:null,destinationHint:null,searchArea:'Austin, TX',origins:{}},preferences:{},hardConstraints:{},cluster:{},sources:{}},
        attendance:Object.fromEntries(people.map(person=>[person.id,{status:'conditional',condition:null,inferred:true}])),
        poll:{eligible:people.map(person=>person.id),approvals:[],changes:[],required:2,threshold:.5,ready:false},listening:'idle',missing:['when.agreed'],
        generation:{status:'idle',runId:null,message:null,missing:[],inputs:null,partial:false,optionCount:0},recommendations:{kind:'venues',venues:[]},pricedMembers:[],pickedId:null,provenance:{}};
      body=planner;
    }
    else if(pathname.endsWith('/messages')){
      if(method==='POST'){
        const speaker=data.demoSpeakerId??'demo-you';const id=`msg-${messages.length+1}`;
        const message={id,from:speaker,text:data.text,sentAt:new Date().toISOString()};messages.push(message);body=message;
        if(planner){
          if(data.text.includes('cannot')){planner.attendance[speaker]={status:'not_going',condition:null,inferred:false};planner.poll.eligible=planner.poll.eligible.filter(id=>id!==speaker);}
          else{planner.attendance[speaker]={status:'going',condition:null,inferred:true};planner.template.when.agreed={label:'Saturday, 7 PM',date:null};planner.template.cluster={meal_type:'dinner',cuisine:['Italian']};planner.template.budget![speaker]=30;planner.template.sources['cuisine:group']='suggested';planner.missing=[];}
          planner.poll.ready=new Set(messages.map(message=>message.from)).size>=Math.ceil(people.length/2);
          planner.revision++;planner.approvalRevision++;
        }
      }else body=messages;
    }
    else if(pathname.endsWith('/planner/respond')&&planner){
      const actor=data.demoSpeakerId??'demo-you';responses.push(data);
      planner.attendance[actor]={status:data.going?'going':'not_going',condition:null,inferred:false};
      if(data.going)planner.poll.approvals.push(actor);else{planner.poll.changes.push(actor);planner.poll.eligible=planner.poll.eligible.filter(id=>id!==actor);}
      planner.revision++;
      if(planner.poll.approvals.length>=2){
        planner.status='approved';planner.pricedMembers=['demo-maya','demo-alex'];planner.generation={...planner.generation,status:'ready',runId:'published-one',optionCount:2};
        planner.recommendations={kind:'venues',venues:[{id:'choice-one',title:'Austin Garden',kind:'restaurant',address:'Austin',rating:4.8,priceLevel:'$$',imageUrl:'https://images.example/venue.jpg',reviewCount:125,url:'https://venue.example',provider:'SerpApi Google Maps',retrievedAt:'2026-10-25T12:00:00Z',fit:null,evidence:[],warnings:[],pickEligible:true},{id:'choice-two',title:'Secondary choice',kind:'restaurant',address:'Austin',rating:4.2,priceLevel:null,url:null,provider:'SerpApi Google Maps',retrievedAt:'2026-10-25T12:00:00Z',fit:null,evidence:[],warnings:[],pickEligible:true}]};
      }
      body=planner;
    }
    else if(pathname.endsWith('/demo/reset')){planner=null;messages.length=0;body={resetAt:new Date().toISOString()};}
    else if(pathname.includes('/me/private')||pathname.includes('/me/checkin')){privateRequests.push(pathname);body={};}
    else if(pathname.endsWith('/planner'))body=planner;
    await route.fulfill({json:body,headers});
  });
  await page.goto('/');
  await page.getByRole('button',{name:'Add to chat'}).click();
  await page.getByRole('menuitem',{name:'Planner',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Start a planner'});
  await dialog.getByLabel('Title',{exact:true}).fill('Saturday dinner');
  await dialog.getByRole('combobox',{name:'Location (optional)'}).fill('Austin');
  await page.getByRole('option',{name:'Austin, TX, USA'}).click();
  await expect(dialog.getByText('Selected from Google Maps')).toBeVisible();
  await expect(dialog.getByRole('radio',{name:'Dining',exact:true})).toBeChecked();
  await page.screenshot({path:info.outputPath('planner-create.png'),fullPage:true});
  await dialog.getByRole('button',{name:'Start planner'}).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'Saturday dinner'})).toBeVisible();
  await expect(page.locator('[aria-label="Live planner template"]')).not.toBeVisible();
  expect(selectedPlaces).toEqual(['austin-city']);
  await page.getByRole('button',{name:'Sam',exact:true}).click();
  await page.getByPlaceholder('Message…').fill('I cannot come.');await page.getByRole('button',{name:'Send',exact:true}).click();
  await expect(page.getByRole('button',{name:'Yes, I’m going',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Maya',exact:true}).click();
  await page.getByPlaceholder('Message…').fill('Saturday at 7 PM works. My budget is $30.');await page.getByRole('button',{name:'Send',exact:true}).click();
  await expect(page.getByRole('button',{name:'Yes, I’m going',exact:true})).toBeVisible();
  await expect(page.locator('[aria-label="Sam: not coming"]')).toBeVisible();
  await expect(page.getByText('Live voting · Have your say')).toHaveCount(1);
  await page.getByRole('button',{name:'Jordan',exact:true}).click();await page.getByRole('button',{name:'Not coming',exact:true}).click();
  await expect(page.locator('[aria-label="Jordan: not coming"]')).toBeVisible();
  await page.getByRole('button',{name:'Maya',exact:true}).click();await page.getByRole('button',{name:'Yes, I’m going',exact:true}).click();
  await expect(page.locator('[aria-label="Maya: confirmed"]')).toBeVisible();
  await page.screenshot({path:info.outputPath('planner-poll.png'),fullPage:true});
  await page.getByRole('button',{name:'Alex',exact:true}).click();await page.getByRole('button',{name:'Yes, I’m going',exact:true}).click();
  await expect(page.getByText('Plan confirmed',{exact:true})).toBeVisible();
  const widget=page.getByRole('region',{name:'Plan recommendation'});
  await expect(widget).toHaveCount(1);await expect(widget).toHaveAttribute('data-phase','ready');
  await expect(widget.getByRole('heading',{name:'Austin Garden'})).toBeVisible();
  await expect(page.getByText('Secondary choice')).toHaveCount(0);
  await expect(page.getByText(/private check-in/i)).toHaveCount(0);
  await expect(widget.getByRole('link',{name:'View place'})).toHaveAttribute('href','https://venue.example/');
  expect(privateRequests).toEqual([]);
  expect(responses.map(response=>response.going)).toEqual([false,true,true]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath('planner-final.png'),fullPage:true});
  await page.getByRole('button',{name:'Reset demo',exact:true}).click();
  await expect(page.getByText('Plan confirmed',{exact:true})).toHaveCount(0);
  await expect(page.getByText('I cannot come.',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Plan recommendation'})).toHaveCount(0);
  await page.getByRole('button',{name:'Add to chat'}).click();await page.getByRole('menuitem',{name:'Planner',exact:true}).click();
  await expect(page.getByLabel('Title',{exact:true})).toHaveValue('');
  expect(errors).toEqual([]);
});
