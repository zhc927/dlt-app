const fs=require('fs'),vm=require('vm'),path=require('path');
const root=path.resolve(__dirname,'..');
const history=JSON.parse(fs.readFileSync(path.join(root,'data/history.json'),'utf8')).draws;
if(!history.length)throw Error('No verified draws');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
let code=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
if(!code)throw Error('Recommendation algorithm missing');
code=code.slice(0,code.indexOf("$('refresh').onclick="));
const context={Math,console};
vm.createContext(context);vm.runInContext(code,context);
const file=path.join(root,'data/recommendations.json');
let store=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):{version:1,records:[]};
const records=store.records,byIssue=new Map(history.map(d=>[d.issue,d]));
let changed=false;
for(const record of records){
  if(record.status==='pending' && byIssue.has(record.issue)){
    const draw=byIssue.get(record.issue);
    record.status='drawn';record.draw={date:draw.date,f:draw.f,b:draw.b};
    record.matches=record.picks.map(p=>({front:p.f.filter(n=>draw.f.includes(n)).length,back:p.b.filter(n=>draw.b.includes(n)).length}));
    changed=true;
  }
}
const last=history.at(-1);
const next=String(Number(last.issue)+1).padStart(last.issue.length,'0');
if(!records.some(r=>r.issue===next)){
  const picks=vm.runInContext('create',context)(history).map(p=>({f:Array.from(p.f),b:Array.from(p.b)}));
  if(picks.length!==5||picks.some(p=>p.f.length!==5||p.b.length!==2))throw Error('Invalid picks');
  records.push({issue:next,based_on:last.issue,created_at:new Date().toISOString(),status:'pending',stake_yuan:10,picks});
  changed=true;
}
if(changed){fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(store,null,2)+'\n');}
console.log('Snapshots:',records.length,'latest:',next,'changed:',changed);
