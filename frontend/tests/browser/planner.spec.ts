import { test, expect } from "@playwright/test";
import type { Planner } from "../../lib/types";

const people = ["Jordan","Maya","Alex","Sam"].map((name,index)=>({id:["demo-you","demo-maya","demo-alex","demo-sam"][index],name,handle:name.toLowerCase(),hue:40+index*60}));
test("planner creation, attributed listening, public perspectives, approval, venues and revision",async({page},info)=>{
  let planner: Planner|null=null;
  let reads=0;
  let messageId=0;
  const messages=[{id:"welcome",from:"demo-you",text:"What should we do together?",sentAt:new Date().toISOString()}];
  const privateRequests:string[]=[];
  const errors:string[]=[];
  page.on("pageerror",e=>errors.push(e.message));
  const headers={"access-control-allow-origin":"*","access-control-allow-headers":"*","access-control-allow-methods":"*"};
  await page.route("**/health",r=>r.fulfill({json:{ok:true,demoMode:true,demoUserId:"demo-you"},headers}));
  await page.route(/\/chats(?:\?|\/|$)|\/trips\//,async route=>{
    const request=route.request(),path=new URL(request.url()).pathname,method=request.method();
    if(method==="OPTIONS"){await route.fulfill({status:204,headers});return;}
    let body:unknown=null;
    const data=method==="POST"||method==="PATCH"||method==="PUT"?request.postDataJSON():{};
    if(path==="/chats")body=[{id:"crew",name:"Weekend crew",group:true,members:people.map(p=>p.id)}];
    else if(path.endsWith("/members"))body=people;
    else if(path.endsWith("/messages")){
      if(method==="POST"){
        const id=`msg-${++messageId}`;
        const speaker=data.demoSpeakerId??"demo-you";
        const message={id,from:speaker,text:data.text,sentAt:new Date().toISOString()};messages.push(message);body=message;
        if(planner){planner.attendance[speaker]={status:"going",condition:null,inferred:true};planner.template.when.flexibility[speaker]=null;
          planner.template.sources[`when.flexibility:${speaker}`]=id;planner.provenance[id]=speaker;
          planner.template.cluster={meal_type:"dinner",cuisine:["Italian"]};planner.template.sources["cuisine:group"]="suggested";
          planner.revision++;planner.approvalRevision++;planner.poll.ready=true;planner.missing=[];}
      }else body=messages;
    }
    else if(path.endsWith("/planners")){
      planner={tripId:"planner-one",title:data.title,topic:data.topic,timezone:data.timezone,revision:0,approvalRevision:0,status:"collecting",
        template:{title:data.title,topic:data.topic,when:{flexibility:{},agreed:null},where:{destination:null,destinationHint:null,searchArea:data.location,origins:{}},preferences:{},hardConstraints:{},cluster:{},sources:{}},
        attendance:Object.fromEntries(people.map(p=>[p.id,{status:"conditional",condition:"hasn't responded yet",inferred:true}])),
        poll:{eligible:people.map(p=>p.id),approvals:[],changes:[],required:2,threshold:.5,ready:false},listening:"idle",missing:["when.agreed"],
        generation:{status:"idle",runId:null,message:null,missing:[],inputs:null,partial:false,optionCount:0},recommendations:{kind:"venues",venues:[]},pricedMembers:[],pickedId:null,provenance:{}};
      body=planner;
    }
    else if(path.endsWith("/planner/approve")&&planner){
      planner.poll.approvals.push(data.demoSpeakerId??"demo-you");planner.revision++;
      if(planner.poll.approvals.length>=2){planner.status="approved";planner.pricedMembers=["demo-maya"];planner.generation.status="ready";planner.generation.optionCount=1;
        planner.recommendations={kind:"venues",venues:[{id:"venue-one",title:"Austin Garden",address:"Austin",rating:4.8,priceLevel:"$$",url:"https://example.org",provider:"SerpApi Google Maps",retrievedAt:"2026-10-25T12:00:00Z",fit:null,evidence:["Provider category: Restaurant"],warnings:["Exact cost unknown; price levels are not dollar quotes."],pickEligible:true}]};}
      body=planner;
    }
    else if(path.endsWith("/planner/pick")&&planner){planner.status="picked";planner.pickedId=data.optionId;planner.revision++;body=planner;}
    else if(path.endsWith("/planner/revise")&&planner){planner.status="collecting";planner.revision++;planner.approvalRevision++;planner.poll.approvals=[];planner.poll.changes=[];planner.pickedId=null;planner.recommendations={kind:"venues",venues:[]};body=planner;}
    else if(path.endsWith("/me/private")){privateRequests.push(path);body={budgetCap:null,dietary:[],accessibility:[],noGos:"",privateScores:{}};}
    else if(path.endsWith("/planner")){reads++;body=planner;}
    else if(path.endsWith("/trips/active"))body=null;
    else if(path==="/trips/planner-one")body={id:"planner-one",chatId:"crew",stage:"options",pickedOptionId:planner?.pickedId??null,yesVotes:0,memberCount:4,checkinsDone:0};
    else if(path.endsWith("/options")||path.endsWith("/facts"))body=[];
    else if(path.endsWith("/options/status"))body={status:"idle"};
    await route.fulfill({json:body,headers});
  });
  await page.goto("/");
  await expect(page.getByText("Public conversation only · private check-in stays yours")).toBeVisible();
  await expect(page.getByRole("button",{name:"Open trip",exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"Add to chat"}).click();
  await page.getByRole("button",{name:"Planner",exact:true}).last().click();
  const modal=page.getByRole("dialog",{name:"Start a planner"});
  await modal.getByLabel("Title",{exact:true}).fill("Friday dinner");
  await modal.getByLabel("City or area (optional)").fill("Austin");
  await modal.getByRole("button",{name:"Start planner"}).click();
  await expect(page.getByRole("heading",{name:"Friday dinner"})).toBeVisible();
  if(info.project.name==="mobile")await page.getByRole("button",{name:"Close",exact:true}).click({position:{x:10,y:10}});
  else await page.getByRole("button",{name:"Planner",exact:true}).first().click();
  await page.getByRole("button",{name:"Maya",exact:true}).click();
  await page.getByPlaceholder("Message…").fill("I’m flexible for dinner.");
  await page.getByRole("button",{name:"Send",exact:true}).click();
  await expect(page.getByRole("button",{name:"Yes, approve"})).toBeVisible();
  await page.getByRole("button",{name:"Yes, approve"}).click();
  await page.getByRole("button",{name:"Alex",exact:true}).click();
  await page.getByRole("button",{name:"Yes, approve"}).click();
  await page.getByRole("button",{name:"Open planner",exact:true}).click();
  await expect(page.getByText("Recommendations include 1 going member.",{exact:false})).toBeVisible();
  await expect(page.getByText("Price level $$",{exact:true})).toBeVisible();
  await expect(page.getByText("From Maya")).toHaveCount(0); // selected Alex has no inferred personal fields
  await page.getByRole("button",{name:"Your private check-in",exact:true}).click();
  await expect(page.getByLabel("Your private budget")).toBeVisible();
  expect(privateRequests).toEqual(["/trips/planner-one/me/private"]);
  expect(reads).toBeGreaterThan(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath("planner.png"),fullPage:true});
  await page.getByRole("button",{name:"Pick this venue"}).click();
  await expect(page.getByRole("button",{name:"Selected",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Revise plan",exact:true}).click();
  await expect(page.getByRole("article",{name:"Austin Garden"})).toHaveCount(0);
  if(info.project.name==="mobile") await page.getByRole("button",{name:"Close planner panel"}).click();
  else await page.getByRole("button",{name:"Planner",exact:true}).first().click();
  await page.getByRole("button",{name:"Yes, approve"}).click();
  await page.getByRole("button",{name:"Maya",exact:true}).click();
  await page.getByRole("button",{name:"Yes, approve"}).click();
  await page.getByRole("button",{name:"Open planner",exact:true}).click();
  await page.getByRole("button",{name:"Pick this venue"}).click();
  await expect(page.getByRole("button",{name:"Selected",exact:true})).toBeVisible();
  await page.getByRole("link",{name:"Open comparison view"}).click();
  await expect(page).toHaveURL(/\/trip\/planner-one/);
  await expect(page.getByRole("heading",{name:"Friday dinner"})).toBeVisible();
  await expect(page.getByRole("article",{name:"Austin Garden"})).toBeVisible();
  expect(errors).toEqual([]);
});
