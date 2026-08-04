import React from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

function App() {
  return (
    <main>
      <section>
        <p className="eyebrow">Dollar TL</p>
        <h1>Административная панель</h1>
        <p>Фундамент Mini App готов. Рабочие разделы появятся в обновлении v0.7.</p>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
