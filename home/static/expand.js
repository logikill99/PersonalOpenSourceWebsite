$(document).ready(function () {
    $('.info').hide();
    $('.skill-button').click(function () {
        let contentwidth = $(this).find(".info").width();
        $('.info').not($(this).find('.info')).hide({queue: true, duration: 100}, "linear")
            .parent('.experience-skills');
        $(this).find('.info').toggle(
            {
                queue: true,
                duration: 100
            }, "linear");

        // $(this).find('.info').animate({
        //     width: '50%',
        //     height: 'fit-content'
        // }, {
        //     queue: false,
        //     duration: 100
        // }).slideToggle();


    });
});