import { test, expect } from '@playwright/test';

const password=process.env.DEV_SEED_PASSWORD;
test.skip(!password,'Requires seed_dev and DEV_SEED_PASSWORD.');

test('teacher creates a course and edits its content using the builder',async({page})=>{
 await page.goto('/login');
 await page.getByLabel('Email').fill('teacher@example.test');
 await page.getByLabel('Пароль',{exact:true}).fill(password!);
 await page.getByRole('button',{name:'Войти',exact:true}).click();
 await page.getByRole('link',{name:'Мои курсы',exact:true}).click();
 await page.getByRole('button',{name:'Создать',exact:true}).click();
 const title='E2E course '+Date.now();
 await page.getByRole('dialog').getByLabel('Название',{exact:true}).fill(title);
 await page.getByRole('combobox',{name:'Дисциплина',exact:true}).selectOption({label:'Прикладная математика'});
 await page.getByRole('dialog').getByRole('button',{name:'Сохранить',exact:true}).click();
 const card=page.getByRole('article').filter({has:page.getByRole('heading',{name:title,exact:true})});
 await card.getByRole('link',{name:'Редактор курса'}).click();
 await page.getByRole('button',{name:'Добавить неделю'}).click();
 await page.getByRole('dialog').getByLabel('Название',{exact:true}).fill('First week');
 await page.getByRole('dialog').getByRole('button',{name:'Сохранить',exact:true}).click();
 await page.getByRole('button',{name:'Добавить тему'}).click();
 await page.getByRole('dialog').getByLabel('Название',{exact:true}).fill('First topic');
 await page.getByRole('dialog').getByRole('button',{name:'Сохранить',exact:true}).click();
 await page.getByRole('button',{name:'+ Материалы',exact:true}).click();
 await page.getByRole('dialog').getByLabel('Название',{exact:true}).fill('First material');
 await page.getByRole('dialog').getByLabel('Контент',{exact:true}).fill('Read this lesson.');
 await page.getByRole('dialog').getByRole('button',{name:'Сохранить',exact:true}).click();
 await page.getByRole('button',{name:'First material',exact:true}).click();
 await expect(page.getByText('Read this lesson.',{exact:true})).toBeVisible();
});
