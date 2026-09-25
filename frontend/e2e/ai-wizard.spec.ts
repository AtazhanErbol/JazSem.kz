import {test,expect} from '@playwright/test';

test('AI wizard reviews and imports a draft without a real provider call',async({page})=>{
 const user={id:'teacher',email:'teacher@example.test',first_name:'Teacher',last_name:'Test',role:'TEACHER',must_change_password:false,preferred_language:'ru'};
 const draft={title:'AI course',description:'Grounded draft',source_gaps:[],weeks:[{title:'Week one',topics:[{title:'Equations',content:'x + 1 = 2',source_chunks:['chunk'],assignments:[{title:'Solve',instructions:'Solve the equation',source_chunks:['chunk']}],questions:[]}]}]};
 let generated=false;let imported=false;let savedTitle='';
 await page.route('**/api/v1/**',async route=>{
  const url=new URL(route.request().url());const path=url.pathname;
  let data:unknown={count:0,results:[],next:null,previous:null};
  if(path.endsWith('/auth/me/'))data=user;
  else if(path.endsWith('/auth/login/'))data={csrfToken:'test-csrf'};
  else if(path.endsWith('/courses/'))data={count:1,results:[{id:'course',title:'My course'}],next:null,previous:null};
  else if(path.endsWith('/sources/'))data={count:1,results:[{id:'source',filename:'lesson.txt',processing_status:'COMPLETED'}],next:null,previous:null};
  else if(path.endsWith('/ai-jobs/')&&route.request().method()==='POST'){generated=true;data={id:'job',status:'COMPLETED'};}
  else if(path.endsWith('/ai-jobs/'))data={count:generated?1:0,results:generated?[{id:'job',status:'COMPLETED'}]:[],next:null,previous:null};
  else if(path.endsWith('/ai-jobs/job/'))data={id:'job',status:'COMPLETED',progress:100,current_step:'DRAFT_READY'};
  else if(path.endsWith('/ai-jobs/job/draft/'))data={id:'draft',data:draft,imported_version:imported?'version':null};
  else if(path.endsWith('/ai-drafts/draft/')&&route.request().method()==='PATCH'){const body=route.request().postDataJSON();savedTitle=body.data.title;draft.title=savedTitle;data={id:'draft',data:draft};}
  else if(path.endsWith('/ai-drafts/draft/confirm/')){imported=true;data={id:'version',status:'DRAFT'};}
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto('/app/ai');
 await page.getByRole('combobox',{name:'Курс',exact:true}).selectOption('course');
 await page.getByRole('button',{name:'Создать черновик',exact:true}).first().click();
 await expect(page.getByRole('heading',{name:'05 / Проверка черновика'})).toBeVisible();
 await page.getByLabel('Название',{exact:true}).first().fill('Reviewed course');
 await page.getByRole('button',{name:'Сохранить',exact:true}).click();
 await expect.poll(()=>savedTitle).toBe('Reviewed course');
 await page.getByRole('button',{name:'Подтвердить черновик',exact:true}).click();
 await page.getByRole('dialog').getByRole('button',{name:'Подтвердить',exact:true}).click();
 await expect.poll(()=>imported).toBe(true);
 await expect(page.getByRole('link',{name:'Редактор курса → Опубликовать'})).toBeVisible();
});
