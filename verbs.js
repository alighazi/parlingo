// One verb per unit (same order as UNITS).
// [infinitive-fa, infinitive-translit, "to …", base, 3rd-person, past, -ing, participle,
//  pastStem-fa, pastStem-tr, presentStem-fa, presentStem-tr]
const VERBS=[
["رفتن","raftan","to go","go","goes","went","going","gone","رفت","raft","رو","rav"],
["داشتن","dâshtan","to have","have","has","had","having","had","داشت","dâsht","دار","dâr"],
["پرسیدن","porsidan","to ask","ask","asks","asked","asking","asked","پرسید","porsid","پرس","pors"],
["خوردن","khordan","to eat","eat","eats","ate","eating","eaten","خورد","khord","خور","khor"],
["دیدن","didan","to see","see","sees","saw","seeing","seen","دید","did","بین","bin"],
["خوابیدن","khâbidan","to sleep","sleep","sleeps","slept","sleeping","slept","خوابید","khâbid","خواب","khâb"],
["پوشیدن","pushidan","to wear","wear","wears","wore","wearing","worn","پوشید","pushid","پوش","push"],
["آمدن","âmadan","to come","come","comes","came","coming","come","آمد","âmad","آی","ây"],
["خریدن","kharidan","to buy","buy","buys","bought","buying","bought","خرید","kharid","خر","khar"],
["رسیدن","residan","to arrive","arrive","arrives","arrived","arriving","arrived","رسید","resid","رس","res"],
["شدن","shodan","to become","become","becomes","became","becoming","become","شد","shod","شو","shav"],
["پریدن","paridan","to fly / jump","fly","flies","flew","flying","flown","پرید","parid","پر","par"],
["ساختن","sâkhtan","to build / make","build","builds","built","building","built","ساخت","sâkht","ساز","sâz"],
["خواندن","khândan","to read","read","reads","read","reading","read","خواند","khând","خوان","khân"],
["فروختن","forukhtan","to sell","sell","sells","sold","selling","sold","فروخت","forokht","فروش","forush"],
["خندیدن","khandidan","to laugh","laugh","laughs","laughed","laughing","laughed","خندید","khandid","خند","khand"],
["برخاستن","barkhâstan","to get up","get up","gets up","got up","getting up","got up","برخاست","barkhâst","برخیز","barkhiz"],
["دویدن","davidan","to run","run","runs","ran","running","run","دوید","david","دو","dav"],
["نواختن","navâkhtan","to play (instrument)","play","plays","played","playing","played","نواخت","navâkht","نواز","navâz"],
["فرستادن","ferestâdan","to send","send","sends","sent","sending","sent","فرستاد","ferestâd","فرست","ferest"],
["پختن","pokhtan","to cook","cook","cooks","cooked","cooking","cooked","پخت","pokht","پز","paz"],
["بخشیدن","bakhshidan","to give / forgive","give","gives","gave","giving","given","بخشید","bakhshid","بخش","bakhsh"],
["نوشتن","neveshtan","to write","write","writes","wrote","writing","written","نوشت","nevesht","نویس","nevis"],
["سوختن","sukhtan","to burn","burn","burns","burned","burning","burned","سوخت","sukht","سوز","suz"],
["راندن","rândan","to drive","drive","drives","drove","driving","driven","راند","rând","ران","rân"],
["پذیرفتن","paziroftan","to accept / receive","accept","accepts","accepted","accepting","accepted","پذیرفت","paziroft","پذیر","pazir"],
["خواستن","khâstan","to want","want","wants","wanted","wanting","wanted","خواست","khâst","خواه","khâh"],
["گفتن","goftan","to say / tell","say","says","said","saying","said","گفت","goft","گوی","guy"],
["شنیدن","shenidan","to hear","hear","hears","heard","hearing","heard","شنید","shenid","شنو","shenav"],
["کاشتن","kâshtan","to plant","plant","plants","planted","planting","planted","کاشت","kâsht","کار","kâr"],
["فهمیدن","fahmidan","to understand","understand","understands","understood","understanding","understood","فهمید","fahmid","فهم","fahm"],
["آموختن","âmukhtan","to learn","learn","learns","learned","learning","learned","آموخت","âmukht","آموز","âmuz"]];
// 9 tense/aspects, taught one per lesson (Lessons 1-9); Lesson 10 reviews all.
const TENSES=[
["Present simple","mi- + present stem + ending — habits & facts","می‌روم — miravam — I go"],
["Present continuous","dâram + present simple — happening right now","دارم می‌روم — dâram miravam — I am going"],
["Present perfect","participle + -am/-i/ast… — done, with present result","رفته‌ام — rafte-am — I have gone"],
["Past simple","past stem + ending — finished past","رفتم — raftam — I went"],
["Past continuous","mi- + past stem + ending — was in progress","می‌رفتم — miraftam — I was going"],
["Past perfect","participle + budam… — had done (before another past)","رفته بودم — rafte budam — I had gone"],
["Future simple","khâham… + past stem — will do","خواهم رفت — khâham raft — I will go"],
["Future continuous","dar hâl-e … khâham bud — will be in the middle of it","در حال رفتن خواهم بود — I will be going"],
["Future perfect","participle + khâham bud — will have done","رفته خواهم بود — I will have gone"]];
const PERSONS=[
["من","man","I"],["تو","to","you"],["او","u","he/she"],["ما","mâ","we"],["شما","shomâ","you (pl./formal)"],["آن‌ها","ânhâ","they"]];
const _PRES_END_TR=["am","i","ad","im","id","and"], _PRES_END_FA=["م","ی","د","یم","ید","ند"],
      _PAST_END_TR=["am","i","","im","id","and"], _PAST_END_FA=["م","ی","","یم","ید","ند"],
      _DAR_TR=["dâram","dâri","dârad","dârim","dârid","dârand"], _DAR_FA=["دارم","داری","دارد","داریم","دارید","دارند"],
      _KHAH_TR=["khâham","khâhi","khâhad","khâhim","khâhid","khâhand"], _KHAH_FA=["خواهم","خواهی","خواهد","خواهیم","خواهید","خواهند"],
      _BUD_TR=["budam","budi","bud","budim","budid","budand"], _BUD_FA=["بودم","بودی","بود","بودیم","بودید","بودند"];
function _pres(v,p){return{fa:"می‌"+v[10]+_PRES_END_FA[p],tr:"mi"+v[11]+_PRES_END_TR[p]}}
function enForm(v,ti,p){
 const pr=["I","you","he/she","we","you (pl./formal)","they"][p], base=v[3],third=v[4],past=v[5],ing=v[6],part=v[7];
 const be=["am","are","is","are","are","are"][p],bePast=["was","were","was","were","were","were"][p],have=["have","have","has","have","have","have"][p];
 return [ `${pr} ${p===2?third:base}`, `${pr} ${be} ${ing}`, `${pr} ${have} ${part}`, `${pr} ${past}`,
          `${pr} ${bePast} ${ing}`, `${pr} had ${part}`, `${pr} will ${base}`, `${pr} will be ${ing}`, `${pr} will have ${part}` ][ti];
}
// Full conjugation of unit verb v at tense ti (0-8) for person p (0-5)
function conjugate(v,ti,p){
 const P=PERSONS[p],partFa=v[8]+"ه",partTr=v[9]+"e";let f;
 if(ti===0)f=_pres(v,p);
 else if(ti===1){let pr=_pres(v,p);f={fa:_DAR_FA[p]+" "+pr.fa,tr:_DAR_TR[p]+" "+pr.tr}}
 else if(ti===2)f={fa:partFa+["‌ام","‌ای"," است","‌ایم","‌اید","‌اند"][p],tr:partTr+["-am","-i"," ast","-im","-id","-and"][p]};
 else if(ti===3)f={fa:v[8]+_PAST_END_FA[p],tr:v[9]+_PAST_END_TR[p]};
 else if(ti===4)f={fa:"می‌"+v[8]+_PAST_END_FA[p],tr:"mi"+v[9]+_PAST_END_TR[p]};
 else if(ti===5)f={fa:partFa+" "+_BUD_FA[p],tr:partTr+" "+_BUD_TR[p]};
 else if(ti===6)f={fa:_KHAH_FA[p]+" "+v[8],tr:_KHAH_TR[p]+" "+v[9]};
 else if(ti===7)f={fa:"در حال "+v[0]+" "+_KHAH_FA[p]+" بود",tr:"dar hâl-e "+v[1]+" "+_KHAH_TR[p]+" bud"};
 else f={fa:partFa+" "+_KHAH_FA[p]+" بود",tr:partTr+" "+_KHAH_TR[p]+" bud"};
 return {fa:f.fa,tr:f.tr,en:enForm(v,ti,p),pronFa:P[0],pronTr:P[1],pronEn:P[2],tense:TENSES[ti][0]};
}
const tenseOfLesson=li=>li<9?li:-1; // -1 = mixed review (Lesson 10)
