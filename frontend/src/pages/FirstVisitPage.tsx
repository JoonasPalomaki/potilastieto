const FirstVisitPage = () => {
  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-sky-400">Ensikäynti</p>
        <h2 className="text-3xl font-bold text-slate-100">Ensikäynnin valmistelu</h2>
        <p className="text-sm text-slate-300">
          Valitse ajanvaraus ja käynnistä potilaan ensikäynti. Täydennä esitiedot, tarkista hoitosuunnitelman tavoitteet ja
          varmista, että potilas on valmis vastaanotolle.
        </p>
      </header>

      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-200">
        <p>
          Ensikäynnin toiminnallisuudet integroidaan tähän näkymään. Valitse ylhäältä ajanvaraus tai potilas ja seuraa
          työkalun ohjeita ensikäynnin avaamiseksi.
        </p>
      </div>
    </section>
  );
};

export default FirstVisitPage;
