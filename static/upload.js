(function (App, $) {

	var Upload = function (opts) {

		if (!(this instanceof Upload)) {
		    return new Upload(opts);
		}

		var upload_target = opts.upload_target;
		var files_target = opts.files_target;
		var finalize_upload_target = opts.finalize_upload_target;
		var $container = $(opts.container);

		var fileAdded = function (file) {
			if(file.fileName.length >= 30) {
				file.fileNameTruncated = file.fileName.substring(0, 27) + '...';
			} else {
				file.fileNameTruncated = file.fileName;
			}
			var html = Mustache.to_html($("#upload-list-template").html(), file);
			$container.find(".files").append(html);
			upload();
		};

		var fileProgress = function (file) {
			var progress = Math.round(r.progress() * 100);
			var liContainer = $('#' + file.uniqueIdentifier);
			liContainer.find('.bar').css('width', progress + '%');
			liContainer.find('.percentage').text(progress + '%');
		};

		var fileError = function (file, message) {
			var liContainer = $('#' + file.uniqueIdentifier);
			liContainer.find('.progress-bar').hide();
			liContainer.find('.err').text(message);
		};

		var cancelFile = function (e) {
			e.preventDefault();
			if(confirm('Are you sure you want to cancel this upload ?')) {
				var uid = $(this).parents('li').attr('id');
				var file = r.getFromUniqueIdentifier(uid);
				file.cancel();
				$(this).parents("li").remove();
			}
		};

		var fileSuccess = function (file) {
			var data = {
				resumableFilename: file.file.name,
				resumableTotalSize: file.file.size,
				resumableIdentifier: file.uniqueIdentifier
			};

			var liContainer = $('#' + file.uniqueIdentifier);
			$.post(finalize_upload_target, data, function (response) {
				if(!response || response.status == 'error') {
					liContainer.find('.err').text(response.message);
					return;
				}

				$.get(files_target, function (data) {
					$container.find('.files-table').html(data);
				});
				liContainer.remove();
			});
		};

		var upload = function () {
			$container.find('.progress-bar').show();
			$container.find('.cancel-file').show();
			window.onbeforeunload = confirmPageLeave;
			r.upload();
		};

		var complete = function () {
			window.onbeforeunload = null;
		};

		var confirmPageLeave = function (e) {
			if(!e) e = window.event;

			var message = 'Are you sure you want to leave this page?';
		    e.cancelBubble = true;
		    e.returnValue = message;

		    if (e.stopPropagation) {
		        e.stopPropagation();
		        e.preventDefault();
		    }
		    return message;
		};

		var r = new Resumable({target: upload_target});
		if(r.support) {
			r.assignBrowse($container.find('.browse'));
			r.assignDrop($container.find('.droptarget'));
			r.on('fileAdded', fileAdded);
			r.on('fileError', fileError);
			r.on('fileProgress', fileProgress);
			r.on('fileSuccess', fileSuccess);
			r.on('complete', complete);

			$container.on('click', '.cancel-file', cancelFile);
		} else {
			$container.find('.upload-container').hide();
			$container.find('.upload-container-not-supported').show();
		}
	};

	App.Upload = Upload;

})(App, $);

