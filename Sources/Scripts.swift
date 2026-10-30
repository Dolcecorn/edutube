import Foundation
import VideoToolbox

/// Código que se inyecta en las páginas, igual que en la versión para TV.
enum Scripts {
    /// Oculta contenedores de anuncios que quedan vacíos tras el bloqueo y salta anuncios de video.
    static let cleanup = """
    (function(){if(window.__tvweb)return;window.__tvweb=1;
    var css='[id^="google_ads"],[id^="div-gpt-ad"],ins.adsbygoogle,.adsbygoogle,[data-ad-slot],'+
     'iframe[src*="doubleclick"],iframe[src*="googlesyndication"],.ad-banner,.ad-container,.ads-container,'+
     '.advertisement,#ad-container,.ytp-ad-overlay-container,.ytp-ad-module,#player-ads,#masthead-ad,'+
     'ytd-ad-slot-renderer,ytd-promoted-video-renderer,ad-slot-renderer,ytm-promoted-sparkles-web-renderer,'+
     'ytm-promoted-video-renderer,ytm-companion-ad-renderer,ytm-companion-slot,ytm-promoted-sparkles-text-search-renderer,'+
     'ytm-statement-banner-renderer,ytm-mealbar-promo-renderer,ytm-paid-content-overlay-renderer,'+
     '.ytm-promoted-sparkles-web-renderer,ytm-rich-item-renderer:has(ad-slot-renderer),'+
     'ytm-item-section-renderer:has(ytm-promoted-sparkles-web-renderer){display:none!important}';
    function add(){var r=document.head||document.documentElement;if(!r)return setTimeout(add,50);
     var s=document.createElement('style');s.textContent=css;r.appendChild(s);}
    add();
    setInterval(function(){
     var b=document.querySelector('.ytp-ad-skip-button,.ytp-ad-skip-button-modern,.ytp-skip-ad-button,.videoAdUiSkipButton,.ytp-ad-skip-button-container button');if(b)b.click();
     var p=document.querySelector('.ad-showing video, .ad-interrupting video');
     if(p&&isFinite(p.duration)&&p.duration>0){p.muted=true;p.currentTime=p.duration;}
    },700);})();
    """

    /**
     Quita los anuncios de las respuestas de YouTube antes de que el reproductor las lea
     (anuncios antes, durante y después del video, y los avisos de la portada y la búsqueda).
     */
    static let youtube = """
    (function(){if(window.__tvyt)return;window.__tvyt=1;
    var AD_KEYS=['adPlacements','playerAds','adSlots','adBreakHeartbeatParams'];
    var AD_ITEMS=['adSlotRenderer','promotedSparklesWebRenderer','promotedVideoRenderer','displayAdRenderer',
     'compactPromotedVideoRenderer','companionAdRenderer','statementBannerRenderer','mealbarPromoRenderer','tvMastheadRenderer'];
    function isAd(x){if(!x||typeof x!=='object')return false;for(var i=0;i<AD_ITEMS.length;i++)if(x[AD_ITEMS[i]])return true;
     var c=x.richItemRenderer&&x.richItemRenderer.content;if(c&&isAd(c))return true;
     var s=x.itemSectionRenderer&&x.itemSectionRenderer.contents;if(s&&s.length&&s.every(isAd))return true;
     var t=x.tileRenderer;return !!(t&&t.contentType==='TILE_CONTENT_TYPE_AD');}
    function clean(o,d){if(!o||typeof o!=='object'||d>40)return o;
     if(Array.isArray(o)){for(var i=o.length-1;i>=0;i--){if(isAd(o[i]))o.splice(i,1);else clean(o[i],d+1);}return o;}
     for(var k=0;k<AD_KEYS.length;k++)if(AD_KEYS[k] in o)delete o[AD_KEYS[k]];
     for(var key in o)if(Object.prototype.hasOwnProperty.call(o,key)&&typeof o[key]==='object')clean(o[key],d+1);return o;}
    var RX=/"(adPlacements|playerAds|adSlots|adSlotRenderer|promotedSparklesWebRenderer|promotedVideoRenderer|displayAdRenderer|compactPromotedVideoRenderer|companionAdRenderer|adBreakHeartbeatParams)"|TILE_CONTENT_TYPE_AD/;
    var P=JSON.parse;JSON.parse=function(t){var r=P.apply(this,arguments);
     try{if(typeof t==='string'&&RX.test(t))clean(r,0);}catch(e){}return r;};
    if(window.Response){Response.prototype.json=function(){return this.text().then(function(t){return JSON.parse(t);});};}
    // En la versión móvil, la primera respuesta viene escrita dentro de la página (var ytInitialPlayerResponse = {...}).
    ['ytInitialPlayerResponse','ytInitialData','ytPlayerResponse'].forEach(function(n){var v;
     try{Object.defineProperty(window,n,{configurable:true,get:function(){return v;},set:function(x){try{v=clean(x,0);}catch(e){v=x;}}});}catch(e){}});
    })();
    """

    /// Avisa a la app cuándo el video está cargando, para mostrar la animación.
    static let buffering = """
    (function(){if(window.__tvbuf||!window.webkit||!webkit.messageHandlers.tvweb)return;window.__tvbuf=1;
    function on(e){if(e.target.tagName==='VIDEO')webkit.messageHandlers.tvweb.postMessage('buffering:1');}
    function off(e){if(e.target.tagName==='VIDEO')webkit.messageHandlers.tvweb.postMessage('buffering:0');}
    ['loadstart','waiting','seeking'].forEach(function(e){document.addEventListener(e,on,true);});
    ['playing','pause','ended','error','emptied','abort'].forEach(function(e){document.addEventListener(e,off,true);});
    })();
    """

    /**
     Hace creer a YouTube que la app sigue a la vista, para que no pause el video al bloquear
     la pantalla o cambiar de app (escuchar música o podcasts con la pantalla apagada).
     */
    static let background = """
    (function(){if(window.__tvbg)return;window.__tvbg=1;
    try{Object.defineProperty(document,'hidden',{get:function(){return false;}});
     Object.defineProperty(document,'visibilityState',{get:function(){return 'visible';}});
     Object.defineProperty(document,'webkitVisibilityState',{get:function(){return 'visible';}});}catch(e){}
    ['visibilitychange','webkitvisibilitychange'].forEach(function(n){
     window.addEventListener(n,function(e){e.stopImmediatePropagation();},true);
     document.addEventListener(n,function(e){e.stopImmediatePropagation();},true);});
    window.__tvwebResume=function(){var v=document.querySelector('video');if(v&&v.__tvwasPlaying&&v.paused)v.play();};
    document.addEventListener('play',function(e){e.target.__tvwasPlaying=true;},true);
    document.addEventListener('pause',function(e){if(!window.__tvwebBg)e.target.__tvwasPlaying=false;},true);
    })();
    """

    /**
     YouTube elige el formato según lo que el navegador dice soportar. Si elige uno que el iPhone
     no decodifica por hardware (AV1 en casi todos, VP9 en los antiguos), el video se calienta y se traba.
     Aquí se le ocultan esos formatos. smooth = true fuerza H.264 a 30 fps.
     */
    static func codec(smooth: Bool) -> (js: String, info: String) {
        let av1 = !smooth && hardware(kCMVideoCodecType_AV1)
        let vp9 = !smooth && hardware(kCMVideoCodecType_VP9)
        let maxFps = smooth ? 30 : 60
        var block: [String] = []
        if !av1 { block.append("av01|av1") }
        if !vp9 { block.append("vp9|vp09|vp8|vp08") }
        let info = (vp9 ? "VP9" : "H.264") + (av1 ? "+AV1" : "") + " hasta 1080p\(maxFps)"
        let rx = block.isEmpty ? "null" : "/\(block.joined(separator: "|"))/"
        let js = """
        (function(){if(window.__tvcodec)return;window.__tvcodec=1;var B=\(rx);
        function ok(t){if(!t)return true;t=String(t).toLowerCase();if(B&&B.test(t))return false;
         var m=/width=(\\d+)/.exec(t);if(m&&+m[1]>1920)return false;
         m=/height=(\\d+)/.exec(t);if(m&&+m[1]>1080)return false;
         m=/framerate=(\\d+)/.exec(t);if(m&&+m[1]>\(maxFps))return false;return true;}
        [window.MediaSource,window.ManagedMediaSource,window.WebKitMediaSource].forEach(function(MS){
         if(MS&&MS.isTypeSupported){var o=MS.isTypeSupported.bind(MS);MS.isTypeSupported=function(t){return ok(t)&&o(t);};}});
        var cp=HTMLMediaElement.prototype.canPlayType;
        HTMLMediaElement.prototype.canPlayType=function(t){return ok(t)?cp.call(this,t):'';};
        })();
        """
        return (js, info)
    }

    private static func hardware(_ codec: CMVideoCodecType) -> Bool {
        VTIsHardwareDecodeSupported(codec)
    }
}
